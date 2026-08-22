# 本番デプロイ失敗: authorized_keys が別プロジェクトに上書きされていた（2026-08-22）

## 症状

master へ push すると GitHub Actions の Deploy が即座に失敗する。

```
ssh: handshake failed: ssh: unable to authenticate,
attempted methods [none publickey], no supported methods remain
```

SSH ハンドシェイクで落ちるため、**デプロイ処理は1行も実行されない**（本番は無傷）。

## 根本原因

VPS の `/home/deploy/.ssh/authorized_keys` に **1行しか無く**、その鍵は
**別プロジェクト shitagoshirae のもの**だった。

```
更新日時: 2026-07-04 19:37
ssh-ed25519 AAAA...VOMH github-actions-deploy@shitagoshirae
```

- k-bar-ai の最後の成功デプロイ = 2026-06-30
- authorized_keys の更新 = 2026-07-04
- **同じVPS・同じ `deploy` ユーザで shitagoshirae のデプロイを設定した際、
  `>>`（追記）ではなく `>`（上書き）で書き込み、k-bar-ai の鍵を消した。**

7/4 以降 k-bar-ai への push が無かったため、**約7週間気づかなかった**。

## 外れた仮説（記録として）

当初は「`appleboy/ssh-action@v1` が浮動タグで自動更新され、RSA鍵の SHA-1 署名
(`ssh-rsa`) が拒否されるようになった」と推測した。**誤り**。

VPS の `sshd -T` を確認したところ `pubkeyacceptedalgorithms` に `ssh-rsa` が
今も含まれていた。**推測で鍵を交換していたら原因を取り違えたまま「直った」ことになり、
再発時に切り分け不能になっていた。** 先に事実を取るべき典型例。

## 対応

1. k-bar-ai 用に **ed25519** 鍵を新規生成
2. `authorized_keys` に **追記**（`>>`）。shitagoshirae の鍵は保持。事前にバックアップ作成
3. 新鍵で `deploy@` にログインできることを**先に検証**
4. GitHub シークレット `VPS_SSH_KEY` を更新
5. 失敗した run を re-run → 成功（4分7秒）
6. 本番 HEAD が `c8da5a5` になり、全コンテナ Up、`/api/v1/health` が
   `{"status":"ok","database":"connected"}` を返すことを確認
7. ローカルの一時秘密鍵を削除

## 再発防止

🔴 **このVPSは k-bar-ai と shitagoshirae で共有されており、デプロイユーザも `deploy` で共通。**
どちらかのデプロイ鍵を設定する時に `authorized_keys` を上書きすると、
**もう一方のデプロイが静かに壊れる。**

- `authorized_keys` は**必ず追記（`>>`）**。`>` は使わない
- 作業前に `cp -a authorized_keys authorized_keys.bak-$(date +%Y%m%d-%H%M%S)`
- 作業後に `ssh-keygen -lf authorized_keys` で**両プロジェクトの鍵が残っているか**確認
- 鍵の comment に用途を書く（`github-actions-deploy@<project>`）

現在の登録内容（2026-08-22 時点・2行）:

```
github-actions-deploy@shitagoshirae (ED25519)
github-actions-deploy@k-bar-ai      (ED25519)
```

## 併せて見つかったセキュリティ問題 → 同日に対応完了

### 発見時の状態

```
permitrootlogin        yes
passwordauthentication yes
```

**root へのパスワードログインがインターネットから可能**で、認証ログには複数の海外IPから
継続的な総当たり攻撃（`Failed password for root`）が記録されていた。
サーバー上には本番DB・`.env`・**2プロジェクト分のデプロイ鍵**があり、
実質「パスワード強度だけが唯一の防御」という状態だった。

### 設定の構造（ここが分かりにくい）

`/etc/ssh/sshd_config` の**12行目**に `Include /etc/ssh/sshd_config.d/*.conf` があり、
**sshd は同じキーワードなら最初に読んだ値を採用する**。したがって drop-in が本体より強い。
読み込み順はファイル名のアルファベット順:

| ファイル | 内容 | 効果 |
|---|---|---|
| `00-passwd.conf` | `PasswordAuthentication yes` | **これが勝っていた**（2026-06-30 作成） |
| `100-allowsshrsa.conf` | `PubkeyAcceptedAlgorithms=+ssh-rsa` | RSA鍵を許可（手元の鍵がRSAのため**触らない**） |
| `50-cloud-init.conf` | `PasswordAuthentication no` | 後読みのため**無視されていた** |
| `sshd_config:42` | `PermitRootLogin yes` | drop-inに定義が無いため有効だった |

### 対応

`00-passwd.conf`（最初に読まれる＝最も強い）を書き換えた:

```
PasswordAuthentication no
PermitRootLogin prohibit-password
```

`prohibit-password` は**公開鍵でのroot接続は維持**する。`no` にすると自分も入れなくなる。
`100-allowsshrsa.conf` は手元のRSA鍵が使えなくなる恐れがあるため**変更していない**。

### 安全手順（締め出し防止）

1. `/root/ssh-backup-<日時>/` に `sshd_config` と `sshd_config.d/` をバックアップ
2. `sshd -t` で構文検証（reload 前）
3. **5分後に自動ロールバックする `nohup` ジョブを仕掛けてから** `systemctl reload ssh`
   （`/root/.ssh-change-confirmed` が無ければ元に戻す）
4. 新規接続で鍵ログイン成功を確認 → 確認ファイルを作成してロールバック解除

`reload` は既存接続を切らない。`restart` は不要。

### 検証結果

- 鍵ログイン: ✅ 成功
- パスワード認証: ✅ `Permission denied (publickey)` で拒否
- **CI デプロイ: ✅ 実際に再実行して成功**（3分47秒）。deploy ユーザは公開鍵認証のため影響なし
- 本番: ✅ HEAD `576a352` / `/api/v1/health` = ok
- 攻撃ログ: 対策後5分間の `Failed password` = **0件**。
  攻撃者は `Connection closed by authenticating user root ... [preauth]` で
  **パスワードを試すことすらできなくなった**

fail2ban はパスワード認証が無効な以上、総当たりが原理的に成立しないため見送り。
