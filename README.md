# FactShecker

بوابة مفتوحة المصدر لرصد الأخبار والادعاءات وتجميع التغطيات المتشابهة، مصممة لتعمل بتكلفة تشغيلية صفرية على GitHub Actions + GitHub Pages.

> **مهم:** FactShecker v0.1 لا يصدر حكمًا آليًا من نوع True/False. النظام يعرض مقدار دعم الأدلة المرصودة ويضع الحالات التي تحتاج تحققًا في قائمة مراجعة.

## كيف تعمل

```text
Google News RSS / public RSS
            ↓
      GitHub Actions
            ↓
  collect + normalize
            ↓
   deduplicate/cluster
            ↓
 evidence-support score
            ↓
      data/index.json
            ↓
       GitHub Pages
```

لا توجد قاعدة بيانات خارجية، ولا API مدفوع، ولا خادم دائم.

## المكونات

- `scripts/collect.py` — يجمع RSS، يوحد البيانات، يحتفظ بآخر 30 يومًا، ويجمع العناوين المتشابهة.
- `sources/sources.json` — قنوات الرصد وقائمة المصادر المنسقة وأوزانها.
- `data/index.json` — قاعدة البيانات الحالية بصيغة JSON.
- `site/` — واجهة عربية static تعمل مباشرة على GitHub Pages.
- `.github/workflows/monitor.yml` — تحديث كل ساعة + نشر Pages.
- `docs/METHODOLOGY.md` — تعريف الـscore والقيود المنهجية.

## التشغيل المحلي

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
python scripts/collect.py
mkdir -p site/data
cp data/index.json site/data/index.json
python -m http.server 8000 -d site
```

ثم افتح `http://localhost:8000`.

## GitHub Pages

بعد دمج الـworkflow في `main`، فعّل GitHub Pages مرة واحدة من:

`Settings → Pages → Build and deployment → Source → GitHub Actions`

بعدها يتولى workflow الجمع والتحديث والنشر تلقائيًا. الجدولة الحالية كل ساعة في الدقيقة 17 لتجنب الضغط المعتاد في بداية الساعة.

## إضافة مصادر

عدل `sources/sources.json`. يدعم v0.1 نوعين:

1. `google_news`: بحث Google News RSS بدون API key.
2. RSS مباشر بإضافة `type` مختلف عن `google_news` وحقول `url`, `name`, `language`.

مثال RSS مباشر:

```json
{
  "name": "Example RSS",
  "type": "rss",
  "url": "https://example.org/feed.xml",
  "language": "ar",
  "limit": 40,
  "enabled": true
}
```

## حالات النظام

| الحالة | المعنى |
|---|---|
| `needs_review` | مصدر واحد ظاهر حاليًا؛ يحتاج مراجعة |
| `medium_evidence` | تغطية مشابهة من مصدرين أو أكثر |
| `corroborated` | تغطية من 3 مصادر أو أكثر مع score كافٍ |

هذه الحالات ليست أحكامًا على صدق الخبر. التفاصيل في [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## خارطة الطريق

- مطابقة semantic متعددة اللغات AR/FR/EN.
- فصل الادعاء عن عنوان الخبر واستخراج claim candidates أدق.
- قاعدة fact-checks منشورة ومطابقة ادعاءات سابقة.
- لوحة مراجعة بشرية عبر GitHub Issues أو ملفات review JSON.
- تتبع provenance للصور والفيديو ومؤشرات C2PA.
- تقييم benchmark قبل نشر أي تصنيف True/False/Misleading.

## التكلفة

المشروع مصمم لمستودع GitHub عام باستخدام standard GitHub-hosted runners وGitHub Pages، بدون خدمات مدفوعة أو مفاتيح API مطلوبة في v0.1.

## License

MIT. راجع `LICENSE`.
