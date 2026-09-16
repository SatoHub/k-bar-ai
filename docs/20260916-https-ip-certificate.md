# HTTPS 化: Let's Encrypt の IPアドレス証明書（160時間）で対応した

実施日: 2026-09-16

## 背景と問題

本番は ConoHa VPS の **IPアドレス直アクセス**（独自ドメインなし）。
nginx で Basic 認証をかけていたが **HTTPS ではなかったため、資格情報が平文で流れていた**。

`docker-compose.prod.yml` では 443 が publish 済み、`certbot-webroot` / `certbot-certs`
ボリュームも定義済みだったが、`nginx.conf` の ssl ブロックは全てコメントアウトされ、
certbot サービスも存在しなかった（雛形だけ置かれた未完成の状態）。

## なぜドメインを取らずに済んだか

**Let's Encrypt は 2026-01-15 に IPアドレス証明書と6日証明書を一般提供開始した。**

- IPアドレス宛の証明書は **shortlived プロファイル必須**（選択の余地なし）
- 有効期間は **160時間（約6.7日）**
- DNS-01 は使えない。HTTP-01 / TLS-ALPN-01 のみ

当初は「ドメインが無いので HTTPS 不可」と判断していたが、これは 2025年時点の前提だった。
**前提が変わったら結論も見直すこと。**

## certbot のバージョン要件でつまずいた点

| 要件 | 実測 |
|---|---|
| `--ip-address` フラグ | certbot **5.3** で追加 |
| **webroot + IPアドレス** | certbot **5.4 以上が必要** |
| VPS にあった certbot | **2.9.0**（Ubuntu 24.04 `noble/universe`） |

**apt では 5.x に到達できない**（`apt-cache madison certbot` の候補は 2.9.0-1 のみ。
noble-backports を有効にしても新版は無い）。

### 採用した方式: Docker コンテナ（`certbot/certbot:v5.8.0`）

snap（公式推奨）と pipx も検討したが、以下の理由でコンテナにした。

- 既存構成が全面 Docker で一致する
- **バージョンがリポジトリに残りレビュー可能**（`docker-compose.prod.yml` に固定）
- snapd を新規導入せずに済む（このVPSには意図的に入っていない）。ディスクは82%使用で余裕が少ない
- イメージは 293MB。取得後もディスク使用率は 82% のまま変化なし

### 旧 apt 版 certbot 2.9.0 は削除した

**残すと事故になる。** `certbot.timer` の `ExecStart=/usr/bin/certbot -q renew` が
2.9.0 を呼ぶため、5.x が書いた `preferred_profile = shortlived` を解釈できず
**更新が静かに失敗する**。160時間証明書ではこれが致命的。

削除前に `apt-get -s remove certbot` で影響を確認し、**`certbot` 単体のみ削除**と判定した
（逆依存に `python3-certbot` と `ntpsec` が出るが Suggests レベル。`/etc/letsencrypt` に
証明書が無かったため ntpsec も certbot の証明書を使っていない）。

手順: `systemctl disable --now certbot.timer` → `apt-get remove -y certbot`

⚠️ `deploy/setup-server.sh` は apt 版 certbot を入れる記述を残している。
新規サーバー構築時にこの手順を踏むと 2.9.0 が復活するため、再構築時は注意。

## 実際の構成

### 証明書

```
/etc/letsencrypt/live/kbar/   ← --cert-name kbar で固定
```

`--cert-name kbar` を使うことで **IPアドレスをパスに埋め込まずに済む**。
将来ドメインを取得しても nginx 設定を書き換えずに移行できる。

取得コマンド（webroot は nginx と共有した named volume）:

```bash
docker run --rm \
  -v docker_certbot-certs:/etc/letsencrypt \
  -v docker_certbot-webroot:/var/www/certbot \
  -v docker_certbot-lib:/var/lib/letsencrypt \
  certbot/certbot:v5.8.0 certonly \
    --non-interactive --agree-tos --register-unsafely-without-email \
    --preferred-profile shortlived \
    --webroot -w /var/www/certbot \
    --ip-address <VPS_IP> \
    --cert-name kbar
```

⚠️ **必ず `--staging` で先に検証する**。本番のレート制限を消費しないため。
検証用証明書は `--cert-name kbar-staging` で取り、確認後に
`certbot delete --cert-name kbar-staging` で削除する
（残すと `certbot renew` がステージング証明書まで更新対象にする）。

### ボリュームの役割

Docker 名は compose のプロジェクト名 `docker` が前置される（compose ファイルが `docker/` にあるため）。

| ボリューム | certbot | nginx |
|---|---|---|
| `docker_certbot-certs` → `/etc/letsencrypt` | 書き込み | `:ro` |
| `docker_certbot-webroot` → `/var/www/certbot` | 書き込み | `:ro` |
| `docker_certbot-lib` → `/var/lib/letsencrypt` | 作業領域 | — |
| `docker_certbot-logs` → `/var/log/letsencrypt` | ログ永続化 | — |

**元々あった named volume の設計は正しかった。** 足りなかったのは certbot サービスだけ。
（ホスト側 certbot を使う前提なら bind mount にすべきだが、apt 版が古くて使えないため
コンテナ方式になり、結果として named volume が正解になった）

`certbot-logs` は後から追加した。**付けないとコンテナ揮発で更新失敗の原因調査ができない。**

### certbot サービスは常駐させない

```yaml
certbot:
  image: certbot/certbot:v5.8.0
  profiles: ["certbot"]   # ← これが無いと up -d で起動して再起動ループになる
```

GitHub Actions のデプロイは `up -d` を実行するため、`profiles` が無いと
即終了するコンテナが延々と再起動される。
`docker compose config --services` に certbot が出ないことを確認済み。

### nginx

- 80番: **ACME challenge のみ認証なしで通し、それ以外は 301 で HTTPS へ**
- 443番: TLSv1.2/1.3 + http2。既存の location をそのまま移植
  （webhook の `auth_basic off`、`/api/` の `proxy_read_timeout 180s`）
- **HSTS は意図的に付けていない**。IPアドレスに対して HSTS は適用されない仕様であり、
  6日証明書の更新失敗時に回復不能になる副作用だけが残る

設定変更はコンテナ再作成ではなく **`nginx -t` → `nginx -s reload`** で反映した
（設定ファイルは bind mount。`-t` が失敗しても稼働中の設定は維持されるので無停止で安全）。

## 更新の自動化

### certbot の更新閾値（重要）

**certbot 4.0.0 以降、更新開始は「残り 1/3 未満」。ただし有効期間10日以下の証明書は「残り 1/2 未満」。**

160時間の証明書なので **残り80時間で更新を開始する**（発行から約80時間後）。
certbot 4.1.0 以降は ARI にも対応するが、**`certbot renew` が走った時にしかチェックしない**
（バックグラウンドで監視するループは無い）。

### タイマー

`/etc/systemd/system/kbar-certbot-renew.timer`（8時間ごと）

```
OnCalendar=*-*-* 02,10,18:17:00
RandomizedDelaySec=20m    # Let's Encrypt の負荷分散ガイドラインに従う
Persistent=true           # VPS停止で取り逃した実行を復帰後に回収する
```

80時間の更新窓に対して8時間間隔＝**窓の中で約10回試行できる**。

### 更新スクリプト `deploy/certbot-renew.sh`

6日証明書では「更新が静かに止まること」が最大のリスクなので3段構えにした。

1. `certbot renew` を実行する
2. **ディスク上の証明書と443で配信中の証明書の `notAfter` を比較し、違っていれば無条件に reload**
3. 配信中の証明書の残り時間が閾値を切っていたら通知

**2が設計上の要点。** 当初は certbot の出力を `Congratulations` 等で grep して
reload を判断していたが、これは以下の理由で捨てた。

- certbot の出力文言が変わると grep が外れ、**reload されないまま「ファイルは新しい・配信は古い」**
  状態で固定される（次回以降 certbot は "not due" を返すので永久に直らない）
- 複数 lineage があると `certbot renew` は1つ失敗しただけで非0を返すため、
  「kbar は成功・他が失敗」で reload に到達しない

期限の比較にすれば**検知と自動復旧が同じ経路になり、文言にも終了コードにも依存しない。**
そのため reload 判定は `certbot renew` の終了コード判定より**先**に置いている。

`WARN_HOURS` の既定は **24**。certbot は残り80時間で更新を開始するので正常時は
残りが72時間程度までしか下がらないが、ARI 由来の窓が使われると更新がもっと遅くなる
可能性がある。**正常動作で鳴る通知は「いつも鳴っている通知」になり本当の停止を見逃すため、
閾値は低め（＝鳴りにくい側）が正しい。** 動作確認用に環境変数で上書きできる。

通知は既存の `NotificationService.push_text` を `docker exec` で呼ぶ。トークンがホストの
`ps` / journal に出ないのが利点。ただし**それだけでは単一障害点**になる
（Docker デーモン停止・backend コンテナ落ち＝まさに通知が必要な局面で通知経路も死ぬ）。
そこで2段のフォールバックを入れた。

- `deploy/line-notify.sh` — curl と python3 だけで LINE API を直叩きする。
  コンテナに依存しない。トークンは argv に出さないよう curl の設定を stdin 経由で渡し、
  本文は 600 の一時ファイルで渡す
- systemd の `OnFailure=kbar-certbot-renew-failed.service` — スクリプト自体が
  起動できない/異常終了した場合に `line-notify.sh` で通知する

## 検証結果

| 項目 | 結果 |
|---|---|
| `https://<IP>/` | 401（Basic認証がHTTPS上で動作）・`ssl_verify_result=0`＝**公的信頼ストアで検証成功** |
| `http://<IP>/` | 301 → `https://<IP>/` |
| 証明書 | issuer `O=Let's Encrypt, CN=YE2`、SAN `IP Address:<IP>`（critical）、ECDSA |
| 有効期間 | Sep 16 03:38:43 → Sep 22 19:38:42 GMT ＝ **正確に160時間** |
| TLS / ALPN | TLSv1.3 / `TLS_AES_256_GCM_SHA384` / `ALPN protocol: h2` |
| LINE webhook | 署名なし・不正署名ともに **400**（401ではない）＝無認証到達かつ署名検証が有効 |
| 認証付きアクセス | フロント 200 / `/api/v1/health` 200（`{"status":"ok","database":"connected"}`） |
| `certbot renew --dry-run --force-renewal` | **"all simulated renewals succeeded"** ＝更新フロー全体が通ることを実証 |
| TLS 暗号スイート | `AES256-SHA256`(PFSなし)で接続すると **handshake failure**＝絞り込みが効いている |
| systemd 経由の実行 | `systemctl start kbar-certbot-renew.service` → `Result=success` / `ExecMainStatus=0`＝**非TTY環境でも `run -T` で動く** |
| **不一致検知→自動reload 分岐** | `disk_notafter` を差し替えた複製で実行し、**不一致検知→reload実行→再比較→🔴通知**まで動作確認。証明書は消費していない |
| コンテナ非依存の通知 | `deploy/line-notify.sh` 単体実行で送信成功（Docker停止時のフォールバック経路） |
| 更新スクリプト本体 | `ディスク上: Sep 22 19:38:42 / 配信中: Sep 22 19:38:42` で一致→reloadせず、残り158時間>24でも警告せず＝**誤警報なし** |

## ハマりどころ・注意点

- **`--dry-run` 単体では何も証明できない。** 期限前だと "No renewals were attempted" で
  終わるため、フローを実証するには `--force-renewal` を併用する
- **`docker run -v <名前>:...` で存在しないボリューム名を書くと Docker が勝手に作る。**
  compose のプロジェクト名前置（`docker_`）を間違えて `kbar_certbot-webroot` という
  空ボリュームを作ってしまった。また `docker run` で先に作ったボリュームは
  compose から見ると管理外で `already exists but was not created by Docker Compose`
  警告が出る。**compose に任せて作らせること**
- **`.gitattributes` に `*.conf text eol=lf` を追加した。** `core.autocrlf=true` では commit 時に
  LF 正規化されるので index に CRLF は入らないが、autocrlf=false の環境でエディタが CRLF を
  書くと VPS 上のファイルと byte 不一致になる。その予防
- 🔴 **Windows の git は実行ビットを記録しない。systemd の `ExecStart` に
  スクリプトを直接書いてはいけない。**
  ローカル(Windows)で `chmod +x` してコミットしても index には `100644` が入る。
  Linux 側の checkout で実行ビットが落ち、`ExecStart=/opt/kbar/deploy/xxx.sh` は
  **`203/EXEC` で起動できなくなる**。160時間証明書では気づかないまま約6.7日で停止する。
  → `ExecStart=/bin/bash /opt/kbar/deploy/xxx.sh` と明示する
  （このリポジトリの他のスクリプトも `bash deploy/xxx.sh` で呼ぶ規約）。
  手元での `systemctl start` は手動 chmod した +x が残っていたため通ってしまい、
  **テストが通ることと本番で通ることが一致しなかった**典型例。
- ⚠️ **`chmod +x deploy/*.sh` をワイルドカードで叩かない。**
  転送対象外のスクリプトにも実行ビットが付き、VPS の git が
  `mode change 100644 => 100755` の差分として検知して作業ツリーが汚れる
  （内容は無変更なのに `git status` が空にならず、デプロイ前の整合確認で混乱する）。
- 🔴 **`.gitattributes` の `eol=lf` は git 経由の checkout しか守らない。**
  今回 Windows の作業コピーが CRLF だった `deploy.sh` / `setup-server.sh` を
  **tar で直接 VPS へ転送してしまい、CRLF のシェルスクリプトを置いた**（88行・71行）。
  index は LF なので git 管理内容は正常だったが、実行すれば `\r` で壊れていた。
  **git を介さずファイルを転送する時は改行を自分で確認すること**
  （`git ls-files --eol` で `w/` 側を見る。`i/lf w/crlf` なら作業コピーが CRLF）
- 平日は JRA 開催が無くレースデータが 0 件なので、**`production-health-check.spec.ts` は
  平日には完走しない**（9件が「テスト可能なレースが存在すること」で失敗する）。
  これは HTTPS とは無関係。土日データでの検証が必要

## 3種のレビューで直した点

`code-reviewer` / `security-reviewer` / `codex`（別モデル）を並行で回し、指摘を差分と
実測に当てて検証してから修正した。主なもの。

| 指摘 | 何が起きるか | 対応 |
|---|---|---|
| **ブートストラップのデッドロック** | 再構築時に証明書が無い→nginx が起動できない→80番が応答しない→証明書が取れない | `nginx.bootstrap.conf`（TLSなし）を追加し、compose の bind mount を `${NGINX_CONF:-./nginx/nginx.conf}` に。`.env` で切り替える |
| **`deploy/deploy.sh` のヘルスチェックが常に成功** | 80番が302を返すので `curl -sf`（`-L`なし）は3xxを成功扱い。backend/frontend が全滅でも「OK」 | upstream を**コンテナ内から直接**叩く形に変更（backend=curl、frontend=busybox wget）。加えて443の証明書配信と80のリダイレクトも検査 |
| **systemd unit がリポジトリに無い** | 再構築で更新機構が消え、約6.7日後に無言でHTTPS停止 | `deploy/systemd/` に3ファイル追加。`deploy.sh` が毎回冪等に設置（unit消失からの自己回復も兼ねる） |
| **`setup-server.sh` が apt版 certbot を再導入** | 2.9.0 と `certbot.timer` が復活し、既知の「静かに失敗」モードが再発 | `apache2-utils` のみに変更。理由をコメントに明記し、ブートストラップ手順も Next steps に追加 |
| **通知がbackendコンテナ依存の単一障害点** | Docker停止時＝通知が最も必要な時に通知できない | `line-notify.sh`（コンテナ非依存）＋ systemd `OnFailure=` の2段フォールバック |
| **reload判定が出力文字列のgrep依存** | 文言変更で reload 漏れ→旧証明書を配信し続ける | 期限の比較方式へ変更（上記） |
| **`ssl_ciphers` 未指定** | 既定の `HIGH:!aNULL:!MD5` はTLS1.2で静的RSA鍵交換(PFSなし)を含み、`prefer_server_ciphers off` で選択権はクライアント側 | ECDHE/CHACHA20 のみに明示。**`AES256-SHA256` が handshake failure で拒否されることを実測確認** |
| **`ssl_session_timeout 1d` + session ticket** | チケット鍵は稼働中ローテートしないため、鍵漏洩時に再開セッションをまとめて復号される | `1h` へ短縮し `ssl_session_tickets off` |
| **`return 301`** | 301はブラウザに恒久キャッシュされ、更新失敗でHTTPSが死んだときHTTPに戻れない。**HSTSを避けた理由と同じ副作用** | `302` に変更 |
| **`WARN_HOURS=48` が誤警報を招く** | ARI由来の窓で更新が遅れると正常動作でも48時間を切り、毎回警告→警告無視の温床 | `24` に下げた |
| **`date -d` 解析失敗で安全網が無言で自己無効化** | 3段目の安全網が消えたことに誰も気づけない | この分岐も通知して `exit 1` |
| **`container_name: kbar-certbot`** | `run --rm` 専用サービスに固定名。前回の run が残ると name 衝突で更新失敗 | 削除 |
| **`nginx:alpine` が未ピン** | certbot を固定した方針と不整合。`http2 on` は 1.25.1+ 必須 | 稼働実績のある `nginx:1.29-alpine` に固定（`mem_limit` も TLS 終端分 64m→128m） |
| **`log()` の `echo "$*"`** | certbot出力が `-n`/`-e` で始まるとオプションとして食われログ欠落 | `printf '%s\n'` へ |
| `.gitignore` に鍵類が無い | PEM を手作業で扱う運用が始まるため `git add -A` 事故の余地 | `*.pem` `*.key` `privkey*` `letsencrypt/` と `.htpasswd.*` を追加 |
| `.gitattributes` のコメントが不正確 | `core.autocrlf=true` では commit 時に LF 正規化されるので「CRLF化してbyte不一致」は実際には起きていなかった | コメントを実態（autocrlf=false 環境での予防）に修正 |

### 指摘したが採用しなかったもの

- **`$host` 反映のオープンリダイレクト**（`code-reviewer` Low）— `security-reviewer` の分析が
  正しく、**同一 host へのリダイレクトなのでオープンリダイレクトにならない**（攻撃者が被害者の
  ブラウザに任意の Host ヘッダを送らせることはできない）。nginx が CR/LF を含む Host を拒否する
  のでヘッダインジェクションも不可。**レビュアー間で見解が分かれた箇所**として記録しておく
- **certbot コンテナのネットワーク隔離 / digest ピン**（`security-reviewer` Medium）— 妥当な指摘だが、
  更新経路は最も壊してはいけない経路なので、投機的な脅威のために今その構造を変えない。後回し
- **webhook の `limit_req`**（同）— `client_max_body_size 256k` は入れたが、レート制限は
  正常な LINE イベントを落とすリスクがあるため保留

## 残っている課題

優先度順。

1. 🔴 **Basic 認証のパスワードをローテーションする（最優先）。**
   HTTPS 化は**遡及的には効かない。** HTTPS にする前、Basic 認証の資格情報は
   Base64（＝平文相当）で HTTP 上を流れていた。経路上の観測者がその期間に取得していれば、
   **HTTPS 化後もその資格情報はそのまま有効**で全画面・全APIにアクセスできる。
   実際に傍受された証跡は確認不能なので、**ローテーションをもって打ち切るのが唯一の対処**。
   対処コストは極小（`htpasswd -B` で再生成してVPS上を差し替え、ブラウザ保存分を更新）。
   併せて旧パスワードを他用途に使い回していないか確認する。
   - ハッシュ形式も未確認。再生成時は `htpasswd -B`（bcrypt）にする。
     既定の MD5-apr1 は現代の基準では弱い
2. **`deploy.yml`（GitHub Actions）に nginx のリロードが無い。**
   `nginx.conf` は bind mount なので、内容だけ変わっても `up -d` ではコンテナが再作成されず
   **新しい設定が読み込まれない**（＝設定変更したつもりで旧設定のまま動き続ける）。
   `deploy/deploy.sh`（手動経路）には `nginx -t` → `reload` を入れたが、
   Actions 側は未対応。⚠️ `.github/workflows/` の push には `workflow` スコープ付きトークンが
   必要（`~/.claude/CLAUDE.md` / memory 参照）なので、実施時は手順に注意
3. **更新の独立監視が無い。** 安全網は `certbot-renew.sh` が実行された時にしか動かない。
   timer 自体が止まれば安全網も止まる（`OnFailure=` はスクリプト異常終了を拾うが、
   timer が disable された場合は何も鳴らない）。backend の scheduler に日次の
   証明書期限チェックジョブを足すのが本筋
4. **HTTPS を守るテストが無い。** `production-health-check.spec.ts` に
   「80が302を返す」「証明書の残り時間が閾値以上」のアサーションが無い
5. **LINE Developers コンソールの webhook URL を確認する。**
   80番は302を返すようになったが**LINE はリダイレクトを追わない。**
   登録URLが `http://` のままなら受信が止まる。なお HTTPS 化以前は 443 に listener が
   無かったため、**そもそも webhook が機能していなかった可能性が高い**（LINE は webhook に
   HTTPS を要求する）。今回初めて機能する条件が整ったので、コンソールで `https://` に設定し
   `Verify` が通ることを確認する
6. **shitagoshirae も同じVPSで 8080 を ufw 開放しており、Basic認証が平文で流れている。**
   `.htpasswd` は MD5-apr1。同じ対応が必要（今回は未対応・ユーザー指示により対象外）
7. VPS の `/opt/kbar/docker/nginx/` に `.htpasswd.bak.<epoch>` という未追跡ファイルが
   2つ放置されている（認証ハッシュを含む）。`.gitignore` に `.htpasswd.*` を追加したので
   今後は ignore されるが、**VPS 上の実ファイルは残っている**ので削除を検討する
8. certbot コンテナのネットワーク隔離と digest ピン（レビュー指摘。更新経路の安定を優先して保留）
9. `nginx.conf` にセキュリティヘッダ（`X-Content-Type-Options` 等）が無い。
   全体が Basic 認証下なので優先度は低いが、外部公開時には必須
