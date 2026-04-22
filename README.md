# Blog Backend API

Bu proje, `FastAPI` ve `Beanie (MongoDB)` kullanan bir blog backend servisidir.  
Kullanıcı kimlik doğrulama, blog yönetimi, yorumlar, kategoriler, etiketler, takip sistemi ve bildirim akışlarını içerir.

## Teknolojiler

- Python
- FastAPI
- Beanie
- MongoDB (PyMongo Async Client)
- JWT (python-jose)
- bcrypt

## Özellikler

- JWT tabanlı kayıt / giriş akışı
- Blog CRUD işlemleri
- Bloglara yorum ekleme ve silme
- Favori blog yönetimi
- Kullanıcı takip / takipten çıkma
- Bildirim listesi ve okunma işaretleme
- Kategori ve etiket (top tags) uçları
- Kapak görseli yükleme (`uploads/` altında saklanır)

## Gereksinimler

- Python 3.11+ (önerilir)
- MongoDB bağlantısı

## Kurulum

1) Depoyu klonlayın ve proje klasörüne girin:

```bash
git clone <repo-url>
cd blog-backend
```

2) Sanal ortam oluşturun ve aktif edin:

```bash
python -m venv .venv
.venv\Scripts\activate
```

3) Bağımlılıkları yükleyin:

```bash
pip install -r requirements.txt
```

4) `.env` dosyası oluşturun:

```env
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=blog_db
JWT_SECRET=buraya-guclu-bir-gizli-anahtar
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
UPLOAD_DIR=uploads
MAX_IMAGE_SIZE_MB=5
```

> Not: `JWT_SECRET` üretmek için güçlü ve uzun bir değer kullanın (ör. Python `secrets.token_hex(32)`).

## Uygulamayı Çalıştırma

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Uç Noktaları (Özet)

### Auth (`/auth`)
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### Blogs (`/blogs`)
- `GET /blogs`
- `GET /blogs/{blog_id}`
- `POST /blogs`
- `PUT /blogs/{blog_id}`
- `DELETE /blogs/{blog_id}`

#### Blog Listeleme Filtreleri (`GET /blogs`)

Desteklenen query parametreleri:

- `skip` (varsayılan: `0`)
- `limit` (varsayılan: `10`, max: `100`)
- `category_id`
- `category` (legacy slug/name desteği)
- `tag`
- `tags` (`tag` için legacy alias)
- `q` (`title` + `content` full-text)
- `search` (`q` için legacy alias)
- `author_id`

Tag filtreleme davranışı:

- Etiket değeri `strip()` ile normalize edilir (baş/son boşluklar temizlenir).
- Büyük/küçük harf duyarsız eşleşir (`Python`, `python`, `PYTHON` aynıdır).
- Tam eşleşme yapılır (`web` araması `websocket` döndürmez).
- Hem string-array (`["python"]`) hem legacy object formatı (`[{"name":"python"}]`) desteklenir.
- Özel karakter içeren etiketlerde güvenli regex kaçışlaması uygulanır.

Örnekler:

```http
GET /blogs?tag=python
GET /blogs?tags=Python
GET /blogs?tag=%20fastapi%20
GET /blogs?q=jwt&tag=security
```

Frontend notu (etikete tekrar tıklama):

- İlk tıkta ilgili etiket ile istek atın: `GET /blogs?tag=<etiket>`
- Aynı etikete tekrar tıklandığında filtreyi kaldırın: `GET /blogs` (tag parametresiz)
- Bu toggle davranışı frontend state tarafında yönetilmelidir; backend stateless çalışır.

### Comments
- `GET /blogs/{blog_id}/comments`
- `POST /blogs/{blog_id}/comments`
- `DELETE /comments/{comment_id}`

### Users (`/users`)
- `GET /users/me`
- `GET /users/me/favorites`
- `POST /users/me/favorites/{blog_id}`
- `DELETE /users/me/favorites/{blog_id}`
- `GET /users/me/following`
- `POST /users/me/following/{target_id}`
- `DELETE /users/me/following/{target_id}`
- `GET /users/{user_id}`
- `PUT /users/{user_id}`
- `GET /users/{user_id}/followers`
- `GET /users/{user_id}/following`
- `GET /users/{user_id}/connections`
- `GET /users/{user_id}/stats`
- `GET /users/{user_id}/posts`

### Categories (`/categories`)
- `GET /categories`
- `GET /categories/{category_id}`
- `POST /categories`
- `DELETE /categories/{category_id}`

### Tags (`/tags`)
- `GET /tags/top`

### Notifications (`/notifications`)
- `GET /notifications`
- `GET /notifications/unread-count`
- `POST /notifications/mark-read`

## Proje Yapısı

```text
blog-backend/
  core/         # config, db bağlantısı, güvenlik, dependency'ler
  models/       # Beanie document modelleri
  routers/      # FastAPI route dosyaları
  schemas/      # Request/response şemaları
  services/     # Yardımcı servisler (örn. dosya saklama)
  uploads/      # Yüklenen dosyalar
  main.py       # Uygulama giriş noktası
```

## Notlar

- `uploads/` klasörü static olarak servis edilir (`/uploads/...`).
- CORS varsayılan olarak `http://localhost:5173` için açıktır.
- Üretim ortamında gizli anahtarlar ve CORS ayarlarını ortam değişkenlerinden yönetin.
