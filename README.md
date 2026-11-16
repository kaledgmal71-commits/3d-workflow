# 3d-workflow — مجسّم رحلة المشروع

تطبيق ويب تفاعلي (PWA يعمل دون اتصال) يعرض **خط الإنتاج القياسي للمشاريع** مجسمًا ثلاثي الأبعاد:
50 غرفة (25 أساسية + 8 ملحقات)، لكل غرفة سير داخلي تتحرك فيه طلبات العمل، مع جولة مرشدة وتجوّل حر،
واسم دولي ومصدر ودرجة اعتماد لكل غرفة (`STANDARDS_MAP.md`)، وتصدير «وثيقة العمل». ومساعد ذكي (Supabase + Claude) يخصص الخط لمشروعك.

## الرابط الحي
`https://kaledgmal71-commits.github.io/3d-workflow/` بعد تفعيل Pages (Settings ← Pages ← Deploy from a branch ← `main` ← `/ (root)`).

## ترتيب الملفات
```
index.html  sw.js  manifest.json  config.js  icon.svg  icon-192.png  icon-512.png   ← التطبيق (تبقى في الجذر)
STANDARDS_MAP.md  README.md  .gitignore
docs/ARCHITECTURE.md
narration/lines.json                       ← نصوص السرد (تُولّد منها حزمة الصوت)
tools/render_narration.py  tools/README_VOICE.md
supabase/migrations/0001_init_blueprint_schema.sql  supabase/migrations/0002_seed_rooms_registry.sql
supabase/functions/plan-project/index.ts
```
ملاحظة: إن رفعت الملفات مسطّحة فانقلها إلى مجلداتها بتغيير المسار من صفحة تحرير الملف (اكتب `المجلد/` قبل اسمه). ملفات التطبيق لا تُنقل.

## المساعد الذكي
مشروع Supabase: `gjxunzwkrnzinimlshyk` (eu-central-1). مضبوط فيه: الجداول بسياسات أمان الصفوف، ودالة `plan-project` التي تتحقق من الدخول، وتحدّ عشر عمليات في الساعة،
وتستدعي Claude ثم **ترفض أي خطة معطوبة أو خبيثة** وتنقّي النصوص.

**ما عليك مرة واحدة:**
1. أضف السر `ANTHROPIC_API_KEY` في Supabase ← Edge Functions ← Secrets (قبله ترد الدالة «الذكاء غير مُهيّأ»).
2. Supabase ← Authentication ← URL Configuration: ضع `https://kaledgmal71-commits.github.io/3d-workflow/` في Site URL وRedirect URLs، وإلا أعاد رابط البريد إلى عنوان آخر.

## أمان
`config.js` يحمل المفتاح **القابل للنشر** (publishable) فقط، لا تضع فيه أي مفتاح سري. كل ما يقترحه الذكاء خارج السجل المعتمد يُوسم «اقتراح غير موثّق مرجعيًا».

## الصوت
انظر `tools/README_VOICE.md`. أسرع طريق: `python tools/render_narration.py --engine edge --asr none` ثم ضع مجلد `audio` بجانب `index.html`. وفي التطبيق زر «تشخيص الصوت».

## حدود صريحة
- لم يُجرّب المساعد الذكي مع Claude نهاية-إلى-نهاية؛ اختُبر منطق التحقق وتطبيق الخطط آليًا بخطط سليمة وخبيثة.
- المحاكاة توضيحية: نسب الفشل افتراضات معلنة وليست إحصاءات.
- الترتيب في خط واحد تركيب لتوضيح التسلسل المعتاد؛ المعيار ISO/IEC/IEEE 12207 لا يفرض نموذج دورة حياة بعينه.
