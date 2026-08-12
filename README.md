# FactShecker

بوابة مفتوحة المصدر لرصد الأخبار والادعاءات وتجميع التغطيات المتشابهة ومطابقة مواد تحقق سابقة، مصممة لتعمل بتكلفة تشغيلية صفرية على GitHub Actions + GitHub Pages.

> **مهم:** FactShecker v0.2 لا يصدر حكمًا آليًا من نوع True/False. النظام يعرض إشارات triage قابلة للتفسير: دعم التغطيات المستقلة، قابلية العنوان للفحص، ومطابقات نصية أولية مع مواد تحقق سابقة.

## الموقع

GitHub Pages: https://ahdmarwan.github.io/FactShecker/

## كيف تعمل

```text
Google News RSS / public RSS
            ↓
      collect + normalize
            ↓
   ┌────────┴─────────┐
   │                  │
news coverage      fact-check feeds
   │                  │
cluster + support   separate corpus
score + claim score   │
   │          previous-check matching
   └────────┬─────────┘
            ↓
      data/index.json
            ↓
       GitHub Pages
```

لا توجد قاعدة بيانات خارجية، ولا API مدفوع، ولا خادم دائم.

## ما الجديد في v0.2

- إزالة suffix الناشر الشائع من عناوين Google News قبل المقارنة.
- `claim_score` heuristics لترشيح العناوين التي تبدو ادعاءات قابلة للفحص، مع أسباب قابلة للتدقيق.
- فصل مواد جهات التحقق عن مصادر corroboration؛ مادة fact-check لا تُحتسب تلقائيًا كمصدر يؤيد الادعاء.
- مطابقة نصية أولية بين clusters ومواد تحقق سابقة باستخدام character similarity + token overlap.
- قنوات مغربية أكثر استهدافًا، بما فيها MAP/Maroc.ma وSNRTnews وقنوات AFP Fact Check/Africa Check.
- CI مستقل للـPull Requests حتى تمر syntax checks وunit tests قبل الدمج.

## المكونات

- `scripts/collect.py` — يجمع RSS، يوحد البيانات، يحتفظ بآخر 30 يومًا، يجمع العناوين المتشابهة، يحسب إشارات triage ويطابق fact-checks.
- `sources/sources.json` — قنوات الرصد وأدوار المصادر وأوزانها.
- `data/index.json` — قاعدة البيانات الحالية بصيغة JSON.
- `site/` — واجهة عربية static تعمل على GitHub Pages.
- `.github/workflows/monitor.yml` — تحديث كل ساعة + نشر Pages.
- `.github/workflows/test.yml` — فحص collector والاختبارات على Pull Requests.
- `docs/METHODOLOGY.md` — تعريف الإشارات والقيود المنهجية.

## التشغيل المحلي

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/collect.py
mkdir -p site/data
cp data/index.json site/data/index.json
python -m http.server 8000 -d site
```

ثم افتح `http://localhost:8000`.

## GitHub Pages

المستودع مضبوط على GitHub Pages عبر GitHub Actions. الـworkflow يجمع البيانات، يحفظ التغييرات الجوهرية في `data/index.json`، يرفع artifact ثم ينشر الموقع.

الجدولة الحالية كل ساعة في الدقيقة 17 لتجنب الضغط المعتاد في بداية الساعة.

## إضافة مصادر

عدل `sources/sources.json`. يدعم النظام:

1. `google_news`: بحث Google News RSS بدون API key.
2. RSS مباشر بإضافة `type` مختلف عن `google_news` وحقول `url`, `name`, `language`.

يمكن للقناة المستهدفة أن تفرض دورًا معروفًا عندما يكون رابط المصدر الذي يرجعه aggregator غير كافٍ للتصنيف:

```json
{
  "name": "Targeted fact-check feed",
  "type": "google_news",
  "query": "site:example.org Morocco",
  "language": "en",
  "source_category": "fact_checker",
  "source_weight": 0.95,
  "enabled": true
}
```

هذا override ينبغي استعماله فقط عندما تكون query نفسها محصورة في المصدر المقصود.

## إشارات النظام

### Evidence-support

- `needs_review`: مصدر دعم واحد ظاهر حاليًا.
- `medium_evidence`: مصدران مستقلان أو أكثر ظاهرون.
- `corroborated`: ثلاثة مصادر دعم أو أكثر مع evidence score كافٍ.

مواد `fact_checker` لا تدخل في حساب هذا الدعم.

### Claim score

يرشّح العناوين القابلة للفحص اعتمادًا على مؤشرات مثل أفعال التصريح، الأرقام والقيم الكمية، مع خفض عناوين السؤال والرأي والتحليل. هذا **check-worthiness score** وليس احتمال صدق.

### Fact-check matches

تُعرض مواد تحقق سابقة عندما يتجاوز التشابه النصي threshold محددًا. المطابقة لا تنقل الحكم القديم إلى الادعاء الحالي؛ يجب مراجعة التاريخ والجهة والكمية والسياق يدويًا.

التفاصيل في [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## خارطة الطريق

- semantic embeddings متعددة اللغات AR/FR/EN مع benchmark قبل الاستعمال الإنتاجي.
- استخراج claim span من النص الكامل بدل الاعتماد على العنوان فقط.
- استرجاع الأدلة الأولية وربط كل claim بـprovenance واضح.
- لوحة مراجعة بشرية وسجل قرارات وتصحيحات.
- تتبع provenance للصور والفيديو ومؤشرات C2PA.
- benchmark منشور قبل أي تصنيف True/False/Misleading.

## التكلفة

المشروع مصمم لمستودع GitHub عام باستخدام standard GitHub-hosted runners وGitHub Pages، بدون خدمات مدفوعة أو مفاتيح API مطلوبة في v0.2.

## License

MIT. راجع `LICENSE`.
