"""Bounded local image decoding/OCR. No provider tokens, ORM or paid APIs."""
import base64
import csv
import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
from .network import fetch,AccessFailure
from .scrapingant import media_reference

MAX_IMAGE_BYTES=4*1024*1024
MAX_PREVIEW_BYTES=40000
MAX_TEXT_BYTES=3500


def read_text(image, *, executable=None):
    from PIL import ImageOps,ImageStat,ImageChops
    command=executable or shutil.which('tesseract')
    if not command:return '',0,'unavailable'
    gray=ImageOps.autocontrast(ImageOps.grayscale(image))
    if ImageStat.Stat(gray).mean[0]<120:gray=ImageOps.invert(gray)
    gray.thumbnail((2000,2400))
    if gray.width<1200:
        ratio=min(2,1200/max(1,gray.width));gray=gray.resize((int(gray.width*ratio),int(gray.height*ratio)))
    gray=ImageOps.expand(gray,border=12,fill=255)
    # Red/coloured lettering disappears in a simple grayscale threshold.
    # A maximum-colour channel preserves it; a smaller second scale also
    # helps very large poster headlines that are oversized for text OCR.
    r,g,b=image.convert('RGB').split()
    coloured=ImageOps.autocontrast(ImageChops.lighter(ImageChops.lighter(r,g),b))
    coloured.thumbnail((800,1100))
    if ImageStat.Stat(coloured).mean[0]<150:coloured=ImageOps.invert(coloured)
    coloured=ImageOps.expand(coloured,border=12,fill=255)
    headline=coloured.copy();headline.thumbnail((420,600))
    variants=[(gray,11),(coloured,11),(headline,11),(coloured.point(lambda p:255 if p>170 else 0),6)]
    best=('',0,'no_text');score=0
    for variant,mode in variants:
        stream=io.BytesIO();variant.save(stream,format='PNG',dpi=(300,300))
        try:
            result=subprocess.run([command,'stdin','stdout','-l','slk+ces+eng','--oem','1','--psm',str(mode),'tsv'],
                input=stream.getvalue(),capture_output=True,timeout=6,
                env={**{k:v for k,v in os.environ.items() if k in ('PATH','LANG','TESSDATA_PREFIX')},'OMP_THREAD_LIMIT':'1'})
            if result.returncode or len(result.stdout)>2*1024*1024:
                if not best[0]:best=('',0,'unavailable')
                continue
            lines={}
            for row in csv.DictReader(io.StringIO(result.stdout.decode('utf-8','replace')),delimiter='\t'):
                word=(row.get('text') or '').strip()
                try:conf=float(row.get('conf','-1'))
                except ValueError:continue
                if not word or conf<25:continue
                key=tuple(row.get(k,'') for k in ('page_num','block_num','par_num','line_num'))
                lines.setdefault(key,[]).append((word,conf))
            # Photo texture often yields dozens of high-ish confidence single
            # letters or punctuation. Those must not beat coherent poster text.
            credible=[];confidence=[];strength=0
            for words in lines.values():
                useful=[(w,c) for w,c in words if sum(ch.isalnum() for ch in w)>=2]
                if not any(sum(ch.isalnum() for ch in w)>=3 for w,c in useful):continue
                credible.append(' '.join(w for w,c in words))
                confidence.extend(c for w,c in useful)
                strength+=sum((c/100)*min(sum(ch.isalnum() for ch in w),15) for w,c in useful)
            text='\n'.join(credible)
            text=''.join(c for c in text if c in '\n\t' or ord(c)>=32).encode()[:MAX_TEXT_BYTES].decode('utf-8','ignore')
            average=sum(confidence)/len(confidence)/100 if confidence else 0
            quality=strength
            if text and quality>score:best=(text,round(average,3),'ready');score=quality
        except subprocess.TimeoutExpired:
            if not best[0]:best=('',0,'timeout')
        except OSError:
            if not best[0]:best=('',0,'unavailable')
    return best


def prepare(raw, *, ocr=read_text):
    import warnings
    from PIL import Image,ImageOps
    if not raw or len(raw)>MAX_IMAGE_BYTES:raise ValueError('image_limit')
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ('JPEG','PNG','WEBP') or source.width*source.height>12000000:
                raise ValueError('unsupported_image')
            source.load();image=ImageOps.exif_transpose(source).convert('RGB')
    image.thumbnail((2000,2400));text,confidence,status=ocr(image)
    preview=image.copy();preview.thumbnail((1400,1600))
    for _ in range(6):
        for quality in (80,65,50,35):
            output=io.BytesIO();preview.save(output,'JPEG',quality=quality,optimize=True)
            data=output.getvalue()
            if len(data)<=MAX_PREVIEW_BYTES:
                return {'preview':base64.b64encode(data).decode(),'width':preview.width,'height':preview.height,
                    'image_hash':hashlib.sha256(data).hexdigest(),'ocr_text':text,'ocr_confidence':confidence,'ocr_status':status,'error':None}
        preview=preview.resize((max(1,int(preview.width*.8)),max(1,int(preview.height*.8))))
    raise ValueError('image_limit')


def capture(url):
    if not media_reference(url):return {'error':'image_denied'}
    try:
        page=fetch(url,max_bytes=MAX_IMAGE_BYTES,timeout=8,media=True)
        if page.status!=200:return {'error':'image_expired' if page.status in (403,404,410) else 'image_network'}
        return prepare(page.body)
    except AccessFailure as error:
        return {'error':'image_expired' if error.category in ('login_required','access_denied') else 'image_network'}
    except Exception:
        return {'error':'image_invalid'}


def bounded(url):
    # The decoder/OCR child receives no gateway key, provider tokens or DB URL.
    env={k:v for k,v in os.environ.items() if k in ('PATH','PYTHONPATH','LANG','SOCIAL_EGRESS_PROXY','TESSDATA_PREFIX')}
    try:
        process=subprocess.Popen([sys.executable,'-m','app.social.acquisition.poster'],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=env,start_new_session=True)
        try:output,_=process.communicate(json.dumps({'url':url}),timeout=38)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.communicate();return {'error':'image_timeout'}
        if process.returncode or len(output.encode())>64000:return {'error':'image_invalid'}
        return json.loads(output)
    except (OSError,ValueError):return {'error':'image_invalid'}


if __name__=='__main__':
    data=json.loads(sys.stdin.buffer.read(2048));print(json.dumps(capture(data['url']),ensure_ascii=False,separators=(',',':')))
