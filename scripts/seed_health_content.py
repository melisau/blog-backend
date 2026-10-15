"""PKOS, IBS ve düşük FODMAP için kaynaklı örnek içerik yükler.

Kullanım (blog-backend klasöründe):
    python scripts/seed_health_content.py

Betik tekrar çalıştırılabilir; aynı başlıktaki yazıları veya aynı slug'a sahip
kategorileri çoğaltmaz. İçerikler tanı veya kişisel tedavi önerisi değildir.
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.database import close_db, init_db  # noqa: E402
from core.security import hash_password  # noqa: E402
from models.blog import Blog  # noqa: E402
from models.category import Category  # noqa: E402
from models.user import User  # noqa: E402


CATEGORIES = (
    {"name": "PKOS (PCOS) ve Beslenme", "slug": "pkos-pcos-beslenme"},
    {"name": "IBS ve Beslenme", "slug": "ibs-beslenme"},
    {"name": "Düşük FODMAP", "slug": "dusuk-fodmap"},
    {"name": "Beslenme Haberleri", "slug": "beslenme-haberleri"},
)

DISCLAIMER = (
    "\n\n> Bu içerik genel bilgilendirme amaçlıdır; tanı veya kişiye özel "
    "beslenme/tedavi önerisi değildir. Belirti, hastalık, gebelik ya da ilaç "
    "kullanımı varsa hekim ve yetkin diyetisyen desteği alınmalıdır."
)

POSTS = (
    {
        "title": "2025 araştırması: PKOS'ta tek bir ‘en iyi diyet’ var mı?",
        "category_slug": "pkos-pcos-beslenme",
        "tags": ["PKOS", "PCOS", "beslenme", "bilimsel araştırma", "DASH"],
        "content": """## Araştırma neyi inceledi?

Şubat 2025'te yayımlanan bir derleme, PKOS'lu kadınlarda farklı beslenme örüntülerini değerlendiren randomize kontrollü çalışmaları karşılaştırdı. İncelenen çalışmaların bir bölümünde enerji kısıtlı DASH yaklaşımı; ağırlık yönetimi ve glikoz kontrolü açısından olumlu sonuçlarla ilişkilendirildi.

## Sonuç nasıl yorumlanmalı?

Bu bulgu, herkesin aynı listeyi uygulaması gerektiği anlamına gelmiyor. PKOS; insülin direnci, uyku, stres, hareket düzeyi, vücut ağırlığı hedefi ve üreme sağlığı gibi birçok etkene göre farklı seyredebilir. Çalışmaların süreleri ve katılımcı özellikleri de birbirinden farklıydı.

Bugünkü kanıtın en güvenli ortak noktası; sürdürülebilir, yeterli lif ve protein içeren, sebze-meyve çeşitliliğini artıran ve kişinin metabolik durumuna göre uyarlanan bir düzenin öne çıkmasıdır. Katı yasak listelerinden çok, uzun süre devam ettirilebilen bir plan önemlidir.

**Kaynak:** [The Influence of Dietary Patterns on Polycystic Ovary Syndrome Management in Women — Nutrients, 13 Şubat 2025](https://pubmed.ncbi.nlm.nih.gov/40005001/)""" + DISCLAIMER,
    },
    {
        "title": "PKOS ve besin destekleri: 2025 meta-analizi bize ne söylüyor?",
        "category_slug": "beslenme-haberleri",
        "tags": ["PKOS", "takviye", "meta-analiz", "kanıta dayalı beslenme"],
        "content": """## Yeni derlemenin odağı

Temmuz 2025'te yayımlanan sistematik derleme ve ağ meta-analizi, PKOS'ta kullanılan çeşitli besin desteklerine ilişkin randomize kontrollü çalışmaları birlikte değerlendirdi. Bazı destekler belirli metabolik veya hormonal ölçümlerde umut verici görünse de araştırmacılar kanıt kalitesi, çalışma büyüklükleri ve sonuçların birbirinden farklı olması nedeniyle temkinli yorum yapılması gerektiğini vurguluyor.

## Pratik mesaj

“Doğal” etiketi bir ürünün herkes için güvenli ya da gerekli olduğu anlamına gelmez. Takviyeler ilaçlarla etkileşebilir, gebelik planında uygun olmayabilir veya gereksiz dozlarda risk oluşturabilir. Ayrıca derleme, PKOS için ideal tek bir beslenme modelinin hâlâ belirlenmediğini hatırlatıyor.

Öncelik; sağlık profesyoneliyle birlikte gereksinimi belirlemek, varsa eksikliği ölçmek ve takviyeyi dengeli beslenmenin yerine koymamaktır.

**Kaynak:** [The effectiveness of nutritional supplements in improving polycystic ovary syndrome in women — Reproductive Biology and Endocrinology, 3 Temmuz 2025](https://link.springer.com/article/10.1186/s12958-025-01409-9)""" + DISCLAIMER,
    },
    {
        "title": "2025 IBS analizi: Diyetler karşılaştırıldığında düşük FODMAP nerede duruyor?",
        "category_slug": "ibs-beslenme",
        "tags": ["IBS", "FODMAP", "bağırsak sağlığı", "meta-analiz"],
        "content": """## 28 çalışma, 2.338 katılımcı

The Lancet Gastroenterology & Hepatology'de 2025 yılında yayımlanan ağ meta-analizi, IBS için 11 farklı beslenme müdahalesini değerlendiren 28 randomize kontrollü çalışmayı bir araya getirdi. Düşük FODMAP yaklaşımı, alışılmış beslenmeyle karşılaştırıldığında genel belirtiler, karın ağrısı ve özellikle şişkinlik açısından yarar gösteren yaklaşımlardan biriydi.

## Neden “tek kazanan diyet” demiyoruz?

Nişasta ve sakkarozu azaltan yaklaşım bazı sıralamalarda öne çıksa da yalnızca iki çalışmada incelenmişti. Düşük FODMAP ise çok daha fazla çalışmada değerlendirilmişti. Araştırmacılar karşılaştırmaların çoğundaki güven düzeyini düşük veya çok düşük olarak sınıflandırdı.

Bu nedenle sonuç, IBS'li herkesin aynı diyete başlaması gerektiği biçiminde okunmamalı. IBS alt tipi, kabızlık/ishal baskınlığı, yeme bozukluğu riski ve mevcut beslenme yeterliliği birlikte değerlendirilmelidir.

**Kaynak:** [Efficacy of dietary interventions in irritable bowel syndrome — Lancet Gastroenterology & Hepatology, 18 Nisan 2025](https://pubmed.ncbi.nlm.nih.gov/40258374/)""" + DISCLAIMER,
    },
    {
        "title": "Düşük FODMAP kalıcı yasak listesi değil: Üç aşamalı güncel yaklaşım",
        "category_slug": "dusuk-fodmap",
        "tags": ["düşük FODMAP", "IBS", "eliminasyon", "yeniden tanıtım"],
        "content": """## 1. Kısa süreli azaltma

Monash Üniversitesi'nin güncel rehberinde ilk aşama, yüksek FODMAP içeren seçeneklerin 2–6 hafta boyunca düşük FODMAP alternatifleriyle değiştirilmesi olarak açıklanıyor. Amaç ömür boyu kısıtlama değil, belirtilerin FODMAP'lara duyarlı olup olmadığını gözlemlemek.

## 2. Yeniden tanıtım

Belirtiler iyileşirse farklı FODMAP grupları planlı biçimde tek tek deneniyor. Böylece kişinin hangi grubu ve ne miktarda tolere ettiği anlaşılmaya çalışılıyor. Rastgele ve aynı anda çok sayıda besini geri eklemek, tetikleyiciyi ayırt etmeyi zorlaştırabilir.

## 3. Kişiselleştirme

Uzun vadeli hedef mümkün olduğunca çeşitli ve en az kısıtlayıcı beslenmedir. Tolere edilen besinler geri eklenir; yalnızca belirti oluşturan tür ve miktarlar sınırlandırılır. Monash, sürecin IBS ve FODMAP konusunda deneyimli bir diyetisyenle yürütülmesini öneriyor.

**Kaynak:** [Starting the Low FODMAP Diet — Monash University, güncel rehber](https://www.monashfodmap.com/ibs-central/i-have-ibs/starting-the-low-fodmap-diet/)""" + DISCLAIMER,
    },
    {
        "title": "Daha nazik FODMAP yaklaşımı kimler için gündemde?",
        "category_slug": "beslenme-haberleri",
        "tags": ["FODMAP Gentle", "IBS", "beslenme çeşitliliği", "Monash"],
        "content": """## Standart eliminasyon herkese uygun olmayabilir

Monash Üniversitesi'nin Aralık 2025 tarihli değerlendirmesi, standart düşük FODMAP protokolünün bazı kişiler için karmaşık veya gereğinden fazla kısıtlayıcı olabileceğine dikkat çekiyor. Lif ve kalsiyum gibi öğelerin yetersiz alınması, besin çeşitliliğinin azalması ve bağırsak mikrobiyotası üzerindeki olası etkiler önemli kaygılar arasında.

“FODMAP Gentle” adı verilen daha nazik yaklaşım, kişinin mevcut beslenmesindeki belirgin yüksek FODMAP kaynaklarını ve bilinen tetikleyicileri hedefleyerek daha sınırlı değişiklik yapmayı amaçlıyor. Bu yöntem de herkes için otomatik çözüm değil; klinik duruma göre seçilmesi gerekiyor.

Ana fikir, en sert kısıtlamayı değil belirtileri yönetmeye yetecek en az kısıtlayıcı yaklaşımı bulmak. Bazı kişiler için diyet dışı seçenekler de değerlendirilmelidir.

**Kaynak:** [The FODMAP Gentle Diet — Monash University, 22 Aralık 2025](https://www.monashfodmap.com/blog/the-fodmap-gentle-diet/)""" + DISCLAIMER,
    },
)


async def get_or_create_editor() -> User:
    username = os.getenv("SEED_EDITOR_USERNAME", "fitbook_saglik").strip()
    email = os.getenv("SEED_EDITOR_EMAIL", "saglik@fitbook.example").strip().lower()
    password = os.getenv("SEED_EDITOR_PASSWORD", "").strip()

    editor = await User.find_one(
        {"$or": [{"email": email}, {"username": username}]}
    )
    if editor:
        return editor
    if len(password) < 12 or password.startswith("replace-"):
        raise ValueError(
            "SEED_EDITOR_PASSWORD en az 12 karakterlik gerçek bir yerel geliştirme "
            "parolası olmalıdır; .env.example değerini doğrudan kullanmayın."
        )
    editor = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        bio="Bilimsel kaynakları sade Türkçeyle özetleyen Fitbook sağlık editörü.",
    )
    await editor.insert()
    return editor


async def seed() -> None:
    await init_db()
    editor = await get_or_create_editor()

    categories: dict[str, Category] = {}
    for item in CATEGORIES:
        category = await Category.find_one(Category.slug == item["slug"])
        if not category:
            category = Category(**item)
            await category.insert()
        categories[item["slug"]] = category

    created = 0
    skipped = 0
    for item in POSTS:
        if await Blog.find_one(Blog.title == item["title"]):
            skipped += 1
            continue
        await Blog(
            title=item["title"],
            content=item["content"],
            author_id=editor.id,
            category=categories[item["category_slug"]],
            tags=item["tags"],
        ).insert()
        created += 1

    print(f"Seed tamamlandı: {created} yazı eklendi, {skipped} yazı zaten vardı.")


async def main() -> None:
    try:
        await seed()
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
