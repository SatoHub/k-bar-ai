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

## 併せて見つかったセキュリティ上の懸念（未対応）

VPS の sshd 設定:

```
permitrootlogin        yes
passwordauthentication yes
```

**root へのパスワードログインがインターネットから可能な状態**で、認証ログには
複数の海外IPから継続的な総当たり攻撃が記録されていた（すべて失敗しているが試行は継続中）。

推奨対応（未実施・要判断）:
- `PasswordAuthentication no`（公開鍵のみに限定）
- `PermitRootLogin prohibit-password` または `no`
- fail2ban の導入

⚠️ 設定変更前に**必ず別セッションで公開鍵ログインできることを確認**すること。
誤るとVPSから締め出される。
