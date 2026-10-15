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

### Sağlık kategorileri ve örnek içerikler

`.env.example` dosyasını `.env` adıyla kopyalayıp MongoDB, JWT ve seed editörü
değerlerini düzenledikten sonra PKOS, IBS ve düşük FODMAP kategorileriyle kaynaklı
örnek içerikleri yükleyebilirsiniz:

```bash
python scripts/seed_health_content.py
```

Betik tekrar çalıştırıldığında aynı başlıkları çoğaltmaz. Örnek sağlık yazıları
genel bilgilendirme amaçlıdır ve her yazıda özgün kaynağa bağlantı verilir.

## Uygulamayı Çalıştırma

### Oturum, yönetici rolü ve hız sınırları

`ACCESS_TOKEN_EXPIRE_MINUTES=30` artık **30 dakika** anlamına gelir. Yeni tokenlarda
`iat` ve `exp` zorunludur; süresi dolmuş, eski `iat` içermeyen veya izin verilenden
uzun ömürlü tokenlar 401 ile reddedilir. Bu değişiklikten önce açılmış oturumlarda
bir kez yeniden giriş gerekir. Mevcut kullanıcı parolaları değiştirilmez.

Kategori oluşturma ve silme yalnızca veritabanındaki `role=admin` olan hesaplara
açıktır. Eski belgelerde rol yoksa `user` kabul edilir. Kayıt ve profil güncelleme
istekleri `role` alanı kabul etmez; JWT içindeki rol bilgisine güvenilmez.
Yazıda kullanılan kategori silinemez (409); listeleme ve görüntüleme herkese açıktır.

Var olan bir hesabın rolünü önce önizleyip sonra uygulamak için:

```bash
python scripts/set_user_role.py --username "kullanici-adi" --role admin
python scripts/set_user_role.py --username "kullanici-adi" --role admin --apply
```

E-posta adresine göre mevcut hesabı kullanmak veya yoksa yeni yönetici oluşturmak için:

```bash
python scripts/provision_admin.py --email "owner@example.com" --username "site owner"
python scripts/provision_admin.py --email "owner@example.com" --username "site owner" --apply
```

Mevcut hesapta parola ve kullanıcı adı korunur. Yeni hesapta rastgele üretilen parola
yalnızca `.env.admin.local` dosyasına yazılır; çıktı ve loglarda gösterilmez.
Bu dosya Git tarafından yok sayılır ve üzerine yazılmaz. Başka bir kullanıcıya ait
meşgul kullanıcı adıyla hesap oluşturulmaz; ilk kayıt olan kişiye otomatik admin verilmez.
Rol yönetim scriptleri yalnızca sunucu/veritabanı yetkisi olan işletmeci tarafından kullanılmalıdır.

Varsayılan sınırlar `.env.example` içindeki karşılıklarıyla ayarlanabilir:

| İşlem | Kimlik | Sınır |
|---|---|---|
| Tüm POST/PUT/PATCH/DELETE istekleri | IP | 120 / 60 saniye |
| Giriş denemeleri | IP | 10 / 60 saniye |
| Giriş denemeleri (başarılı olanlar dahil) | Normalize edilmiş e-posta | 10 / 300 saniye |
| Kayıt denemeleri | IP | 10 / 3600 saniye |
| Yazı oluşturma/güncelleme | Kullanıcı | 10 / 60 saniye |
| Yorum oluşturma | Kullanıcı | 20 / 60 saniye |

İlgili sınırlar birlikte uygulanır. Sabit zaman pencereleri kullanılır; pencere
sınırında kısa sürede iki pencerenin bütçesi kullanılabilir. NAT arkasındaki kişiler
IP bütçesini paylaşır. Başarısız denemeler de sayılır; hesap bazlı giriş sınırı
IP değiştirerek deneme yapmayı kısıtlar, ancak sınır dolduğunda hesap sahibi de
`Retry-After` süresini bekler. Gerekirse gerçek trafiğe göre eşikleri ayarlayın.

Sayaçlar MongoDB'deki `rate_limit_buckets` koleksiyonunda atomik olarak artırılır;
worker'lar ve yeniden başlatmalar arasında ortak bütçe korunur. Kimlikler açık metin
yerine SHA-256 özeti olarak kaydedilir. `expires_at` TTL indeksi eski sayaçları
temizler; pencere yenilenmesi TTL silme zamanına bağlı değildir. Sınır aşıldığında
429 ve `Retry-After` döner. Sayaç veritabanına erişilemiyorsa koruma sessizce
kapatılmadan yazma işlemleri 503 ile reddedilir. GET ve CORS preflight istekleri
bu yazma limitine dahil değildir. MongoDB kullanıcısının bu koleksiyona yazma ve
TTL indeksi oluşturma yetkisi olmalıdır.

IP için doğrudan `X-Forwarded-For` okunmaz. Reverse proxy kullanıyorsanız Uvicorn'un
güvendiği proxy adreslerini dağıtımınıza göre ayarlayın (`--forwarded-allow-ips`);
internet istemcilerinin kendi IP başlığını belirlemesine izin vermeyin. HTTPS,
edge/WAF korumaları ve HTTP gövde boyutu limitleri ayrıca altyapıda yapılandırılmalıdır.

### Güvenlik testleri

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Bu komut, gerçek uygulama verilerine dokunmadan JWT, rol, API yetkilendirmesi ve
429/CORS davranışını test eder; Mongo entegrasyon testleri varsayılan olarak atlanır.
Gerçek MongoDB üzerinde ortak sayaç ve pencere yenilenmesini test etmek için PowerShell:

```powershell
$env:RUN_MONGO_TESTS = '1'
python -m unittest discover -s tests -v
```

Entegrasyon testleri yalnızca kendilerinin rastgele isimle oluşturduğu
`security_test_limits_<uuid>` koleksiyonlarını kullanır ve sonunda kaldırır.
Mevcut kullanıcıları, yazıları ve kategorileri değiştirmez.

Uygulama referansları: [FastAPI route bağımlılıkları](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/),
[MongoDB atomik güncellemeler](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/update/),
[MongoDB TTL davranışı](https://www.mongodb.com/docs/manual/core/index-ttl/).

### Sunucuyu başlatma

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
