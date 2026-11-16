#!/usr/bin/env python3
"""
أداة تسجيل السرد: تحوّل narration/lines.json (المُصدَّر من التطبيق) إلى حزمة صوت جاهزة
audio/<id>.ogg + audio/index.json يقرؤها التطبيق تلقائيًا ويشغّلها بدل صوت المتصفح.

الفكرة: لكل سطر نولّد عدة محاولات (بذور seeds مختلفة)، ثم نعيد سماع كل محاولة بمحرك تعرّف
على الكلام ونقارنها بالنص (نسبة خطأ الحروف CER)، ونعتمد الأقرب. ما يتجاوز العتبة يُعلَّم للمراجعة البشرية.

المحركات:
  silma  : SILMA TTS v1 (واجهة SilmaTTS.infer كما في صفحة الحزمة على PyPI). يحتاج: pip install silma-tts + ffmpeg.
           يستنسخ نبرة من تسجيل مرجعي قصير؛ استعمل تسجيلًا لمتحدث وافق صراحةً، واذكر أن الصوت مولَّد بالذكاء الاصطناعي.
  edge   : أصوات مايكروسوفت العصبية عبر مكتبة edge-tts (pip install edge-tts): أسرع طريق لصوت جيد بلا معالج رسوميات؛ يحتاج إنترنت أثناء التسجيل فقط.
           الصوت الافتراضي ar-SA-HamedNeural (ذكر). الخدمة غير رسمية وشروطها لا تضمن النشر التجاري؛ للنشر التجاري استعمل Azure AI Speech المرخّص.
  mock   : محرك وهمي لاختبار الأنبوب فقط (لا صوت حقيقي).
التعرّف: faster-whisper (large-v3) أو mock.
"""
import argparse, json, os, re, shutil, struct, subprocess, sys, wave, math

def fnv1a(text: str) -> str:
    h = 0x811C9DC5
    for b in text.encode('utf-8'):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return format(h, '08x')

_DIAC = re.compile('[\u064B-\u0652\u0670\u0640]')
def norm_ar(t: str) -> str:
    t = _DIAC.sub('', t)
    t = re.sub('[أإآٱ]', 'ا', t).replace('ى', 'ي').replace('ة', 'ه')
    return re.sub(r'[^\u0621-\u064A0-9A-Za-z]', '', t)

def cer(ref: str, hyp: str) -> float:
    a, b = norm_ar(ref), norm_ar(hyp)
    if not a: return 0.0 if not b else 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(a)

class Mock:
    ext = 'wav'
    def synth(self, text, seed, path):
        n = int(24000 * max(1.0, len(text) * 0.06))
        with wave.open(path, 'w') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(b''.join(struct.pack('<h', int(3000 * math.sin(i / 20))) for i in range(0, n, 4)) )
    def asr(self, path, text):
        seed = int(re.search(r'_s(\d+)', path).group(1))
        return text if seed % 3 == 0 else text[: max(1, len(text) // 2)]

class Silma:
    ext = 'wav'
    def __init__(self, a):
        from silma_tts.api import SilmaTTS
        self.m, self.a = SilmaTTS(), a
    def synth(self, text, seed, path):
        self.m.infer(ref_file=self.a.ref, ref_text=self.a.ref_text, gen_text=text,
                     file_wave=path, seed=seed, speed=self.a.speed)

class Edge:
    ext = 'mp3'
    def __init__(self, a):
        self.voice, self.rate = a.voice, a.rate
    def synth(self, text, seed, path):
        import asyncio, edge_tts
        asyncio.run(edge_tts.Communicate(text, self.voice, rate=self.rate).save(path))

class NoAsr:
    def asr(self, path, text):
        return text

class Whisper:
    def __init__(self):
        from faster_whisper import WhisperModel
        self.m = WhisperModel('large-v3')
    def asr(self, path, text):
        segs, _ = self.m.transcribe(path, language='ar', vad_filter=True)
        return ' '.join(s.text for s in segs)

def to_ogg(wav, ogg):
    if not shutil.which('ffmpeg'): return False
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-af',
        'loudnorm=I=-16:TP=-1.5:LRA=11,apad=pad_dur=0.25', '-c:a', 'libopus', '-b:a', '48k', ogg])
    return r.returncode == 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--lines', default='../narration/lines.json'); p.add_argument('--out', default='../audio')
    p.add_argument('--engine', choices=['silma', 'edge', 'mock'], default='silma'); p.add_argument('--asr', choices=['whisper', 'mock', 'none'], default='whisper')
    p.add_argument('--voice', default='ar-SA-HamedNeural'); p.add_argument('--rate', default='-5%')
    p.add_argument('--ref'); p.add_argument('--ref-text', default=None)
    p.add_argument('--seeds', type=int, default=5); p.add_argument('--speed', type=float, default=0.95)
    p.add_argument('--cer-max', type=float, default=0.08); p.add_argument('--force', action='store_true')
    p.add_argument('--check-only', action='store_true')
    a = p.parse_args()
    L = json.load(open(a.lines, encoding='utf-8'))
    bad = [l['id'] for l in L if fnv1a(l['text']) != l['id']]
    print(f'{len(L)} سطرًا؛ عدم تطابق المعرّفات: {len(bad)}')
    if a.check_only or bad: sys.exit(1 if bad else 0)
    os.makedirs(a.out, exist_ok=True)
    eng = {'mock': Mock, 'edge': Edge, 'silma': Silma}[a.engine]() if a.engine == 'mock' else (Edge(a) if a.engine == 'edge' else Silma(a))
    asr = {'mock': Mock, 'none': NoAsr}[a.asr]() if a.asr in ('mock', 'none') else Whisper()
    if a.engine == 'edge': a.seeds = 1
    ip = os.path.join(a.out, 'index.json')
    idx = json.load(open(ip)) if os.path.exists(ip) else {}
    rep = []
    for n, l in enumerate(L, 1):
        ogg = os.path.join(a.out, l['id'] + '.ogg')
        if l['id'] in idx and not a.force and os.path.exists(os.path.join(a.out, os.path.basename(idx[l['id']]))): continue
        best = None
        for s in range(a.seeds):
            tmp = os.path.join(a.out, f"_{l['id']}_s{s}.{eng.ext}")
            eng.synth(l['prep'], s, tmp)
            c = cer(l['prep'], asr.asr(tmp, l['prep']))
            if best is None or c < best[0]:
                if best: os.remove(best[2])
                best = (c, s, tmp)
            else: os.remove(tmp)
            if c <= 0.02: break
        c, s, tmp = best
        ok = to_ogg(tmp, ogg)
        fin = ogg if ok else os.path.join(a.out, l['id'] + '.' + eng.ext)
        if not ok: os.replace(tmp, fin)
        else: os.remove(tmp)
        idx[l['id']] = 'audio/' + os.path.basename(fin)
        rep.append({'id': l['id'], 'cer': round(c, 4), 'seed': s, 'review': c > a.cer_max, 'text': l['text']})
        print(f'[{n}/{len(L)}] {l["id"]} cer={c:.3f} seed={s}' + ('  <- راجِعه بالسمع' if c > a.cer_max else ''))
        json.dump(idx, open(ip, 'w'), ensure_ascii=False, indent=1)
    json.dump(rep, open(os.path.join(a.out, 'report.json'), 'w'), ensure_ascii=False, indent=1)
    print('تم. السطور التي تحتاج مراجعة بشرية:', sum(r['review'] for r in rep))

if __name__ == '__main__':
    main()
