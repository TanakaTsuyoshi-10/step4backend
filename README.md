# Tanaka POS Backend API

WebモバイルPOS（Lv2）システムのバックエンドAPI。FastAPI + SQLAlchemy + Azure Database for MySQLで構築。

## 機能

- 商品検索API (`GET /api/v1/products/{code}`)
- 取引登録API (`POST /api/v1/trades`)
- 税計算（10%, 8%, 0%対応）
- ヘルスチェック (`GET /health`)
- OpenAPI仕様書 (`GET /docs`)

## 環境要件

- Python 3.9+
- Azure Database for MySQL (Flexible Server)
- SSL/TLS接続必須

## セットアップ

### 1. 依存関係インストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数設定

```bash
export DATABASE_URL="mysql+aiomysql://username:password@host:3306/tanaka_pos?charset=utf8mb4"
export SQL_ECHO="false"  # 本番環境ではfalse推奨
```

### 3. データベース初期化

```bash
# Alembic マイグレーション実行
alembic upgrade head
```

### 4. アプリケーション起動

```bash
# 開発環境
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 本番環境
gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 環境変数と接続例

### Azure Database for MySQL SSL接続設定

#### 例A: 最小構成（簡易）
デフォルトの設定。大部分の環境で動作します。

```python
# app/db.py
connect_args={
    "charset": "utf8mb4",
    "autocommit": False,
    "ssl": True,  # Azure Database for MySQL requires SSL/TLS
}
```

#### 例B: 厳密構成（推奨）
CA証明書を明示的に指定する方法。SSL証明書の問題が発生する場合に使用。

```python
# app/db.py
import ssl
import certifi

def create_ssl_context():
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    ssl_context.check_hostname = False  # Azure MySQLでは通常False
    ssl_context.verify_mode = ssl.CERT_REQUIRED  # 証明書検証は必須
    return ssl_context

connect_args={
    "charset": "utf8mb4",
    "autocommit": False,
    "ssl": create_ssl_context(),  # 厳密なSSL設定
}
```

### 切替え基準

1. **まず `ssl=True`** で接続を試行
2. **CA解決の問題**（証明書エラー等）が発生した場合は、`certifi`を使う厳密構成に切替え
3. 本番環境では厳密構成を推奨

## 動作確認手順

### 1. アプリケーション起動確認
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. ヘルスチェック
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "service": "tanaka-pos-api"}
```

### 3. 商品検索API確認
```bash
# 事前に商品マスタにデータを投入してから実行
curl http://localhost:8000/api/v1/products/1234567890123
# Expected: 商品情報JSON または 404エラー
```

### 4. OpenAPI仕様確認
```bash
curl http://localhost:8000/docs
# Expected: Swagger UIの表示
```

## Azure App Service デプロイ

### 必要な環境変数

| 変数名 | 値例 | 説明 |
|--------|------|------|
| `WEBSITES_PORT` | 8000 | FastAPIポート |
| `DATABASE_URL` | `mysql+aiomysql://...` | DB接続文字列 |
| `SQL_ECHO` | false | SQLログ出力 |

### スタートアップコマンド

```bash
gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120
```

## API仕様

詳細は `/docs` エンドポイントのOpenAPI仕様書を参照してください。

### 主要エンドポイント

- `GET /api/v1/products/{code}` - 商品検索
- `POST /api/v1/trades` - 取引登録
- `GET /health` - ヘルスチェック

## トラブルシューティング

### SSL接続エラーの場合
1. `ssl=True` から `ssl=create_ssl_context()` に変更
2. `certifi` パッケージがインストールされていることを確認

### DB接続エラーの場合
1. 環境変数 `DATABASE_URL` の設定確認
2. Azure MySQLのファイアウォール設定確認
3. VNet統合の設定確認

## ライセンス

本プロジェクトは内部開発用です。