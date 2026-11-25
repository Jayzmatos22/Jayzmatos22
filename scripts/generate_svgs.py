"""Gera os SVGs animados do README do perfil (tema verde / terminal).

Uso:   python scripts/generate_svgs.py --photo caminho/para/foto.jpg
Requer Pillow. Saída em assets/: header, títulos de seção, stack, barras de janela e divisor.
As animações usam SMIL + CSS dentro do próprio SVG, que o GitHub exibe como imagem.
"""
import argparse
import base64
import io
import math
import random
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

BG, PANEL, BAR = "#020303", "#050807", "#0a0f0d"
LINE, LINE2 = "#1d2924", "#2b3933"
TEXT, TEXT2, MUTED, DIM = "#ecf3ee", "#b9c5be", "#7f8c85", "#4c5852"
ACC, ACC_HI, AMBER, RED, GREEN_DOT = "#3dff7a", "#dfffe8", "#ffb547", "#ff5f57", "#3ddc6b"
MONO = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,'DejaVu Sans Mono',monospace"
SANS = "'Sora','Segoe UI',Inter,'Helvetica Neue',Arial,sans-serif"
CW = 0.6  # largura de um caractere monoespaçado / tamanho da fonte
NBSP = " "
RAMP = " .:-=+*xo#%@"
GLITCH = "01<>/\\{}[]$#_=+"

_counter = [0]


def uid(prefix):
    _counter[0] += 1
    return f"{prefix}{_counter[0]}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


BASE_CSS = """
text { font-family: %s; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }
""" % MONO


def svg_doc(w, h, body, css="", defs="", label=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">\n'
        f"<style>{BASE_CSS}{css}</style>\n<defs>{defs}"
        '<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect y="2" width="4" height="1" fill="#000" opacity=".35"/></pattern>'
        '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f"</defs>\n{body}\n</svg>\n"
    )


def typed(x, y, parts, size, begin, mode="type", speed=0.045, family=MONO, weight=None, width=None):
    """Texto revelado por um clip animado. mode='type' (caractere a caractere) ou 'wipe'."""
    text = "".join(t for t, _ in parts)
    n = max(1, len(text))
    w = width or n * size * CW
    full = w + 8
    cid = uid("c")
    if mode == "type":
        dur = max(0.05, n * speed)
        values = ";".join(f"{full * i / n:.1f}" for i in range(n + 1))
        keys = ";".join(f"{i / n:.4f}" for i in range(n + 1))
        anim = (f'<animate attributeName="width" values="{values}" keyTimes="{keys}" calcMode="discrete" '
                f'dur="{dur:.2f}s" begin="{begin:.2f}s" fill="freeze"/>')
    else:
        dur = 0.45
        anim = (f'<animate attributeName="width" values="0;{full:.1f}" keyTimes="0;1" calcMode="spline" '
                f'keySplines="0.16 1 0.3 1" dur="{dur}s" begin="{begin:.2f}s" fill="freeze"/>')
    clip = (f'<clipPath id="{cid}"><rect x="{x - 4}" y="{y - size * 1.1:.1f}" height="{size * 1.6:.1f}" width="0">'
            f"{anim}</rect></clipPath>")
    spans = "".join(f'<tspan fill="{fill}">{esc(t.replace(" ", NBSP))}</tspan>' for t, fill in parts)
    wt = f' font-weight="{weight}"' if weight else ""
    el = (f'<text x="{x}" y="{y}" font-size="{size}" style="font-family:{family}"{wt} textLength="{w:.1f}" '
          f'lengthAdjust="spacingAndGlyphs" clip-path="url(#{cid})">{spans}</text>')
    return clip, el, begin + dur


def cursor(x, y, size, begin):
    return (f'<rect x="{x:.1f}" y="{y - size * 0.92:.1f}" width="{size * 0.6:.1f}" height="{size * 1.15:.1f}" fill="{ACC}" opacity="0" filter="url(#glow)">'
            f'<animate attributeName="opacity" values="1;0;1" keyTimes="0;0.5;1" calcMode="discrete" dur="1.05s" '
            f'begin="{begin:.2f}s" repeatCount="indefinite"/></rect>')


def window_chrome(w, h, title, right=""):
    return (
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{PANEL}" stroke="{LINE}"/>'
        f'<path d="M12.5 0.5 H{w - 12.5} A12 12 0 0 1 {w - 0.5} 12.5 V40 H0.5 V12.5 A12 12 0 0 1 12.5 0.5 Z" fill="{BAR}"/>'
        f'<path d="M0.5 40.5 H{w - 0.5}" stroke="{LINE}"/>'
        f'<circle cx="22" cy="20.5" r="5.5" fill="{RED}"/><circle cx="40" cy="20.5" r="5.5" fill="{AMBER}"/>'
        f'<circle cx="58" cy="20.5" r="5.5" fill="{GREEN_DOT}"/>'
        f'<text x="{w / 2}" y="25" text-anchor="middle" font-size="12" fill="{TEXT2}">{esc(title)}</text>'
        f'<text x="{w - 18}" y="25" text-anchor="end" font-size="11" fill="{DIM}">{esc(right)}</text>'
    )


# --------------------------------------------------------------------------- ASCII
def smooth(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def ink(img, cols, rows):
    """Mesma matemática do retrato do portfólio (src/portrait/ascii.ts)."""
    px = list(img.convert("RGB").resize((cols, rows), Image.BILINEAR).getdata())
    lum = [(0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 for r, g, b in px]
    bw, bh = max(2, round(cols * 0.12)), max(2, round(rows * 0.08))
    acc, n = [0.0, 0.0, 0.0], 0
    for y in range(bh):
        for x in range(cols):
            if bw <= x < cols - bw:
                continue
            for c in range(3):
                acc[c] += px[y * cols + x][c]
            n += 1
    bg = [a / n for a in acc]
    values = []
    for y in range(rows):
        for x in range(cols):
            i = y * cols + x
            fg = smooth(22, 62, math.dist(px[i], bg))
            L = lum[i]
            right, down = lum[y * cols + min(cols - 1, x + 1)], lum[min(rows - 1, y + 1) * cols + x]
            detail = min(1.0, (abs(L - right) + abs(L - down)) * 2.2)
            vig = 1 - smooth(0.8, 1.15, math.hypot((x / cols - 0.5) / 0.56, (y / rows - 0.46) / 0.6))
            tone = smooth(0.04, 0.92, L ** 1.1)
            subject = max(tone, 0.16 + detail * 0.5)
            values.append(max(0.0, min(1.0, (fg * subject + (1 - fg) * tone * 0.1) * vig)))
    return values


def ascii_row_spans(row_values):
    """Agrupa caracteres por densidade: fraco (verde apagado), médio (verde), denso (quase branco)."""
    spans, current, buf = [], None, ""
    for v in row_values:
        idx = round(v * (len(RAMP) - 1))
        ch = RAMP[idx]
        level = "s" if ch == " " else ("lo" if idx <= 4 else ("mid" if idx <= 8 else "hi"))
        if level != current and buf:
            spans.append((current, buf))
            buf = ""
        current = level
        buf += NBSP if ch == " " else ch
    if buf:
        spans.append((current, buf))
    style = {"s": "", "lo": f' fill="{ACC}" fill-opacity=".42"', "mid": f' fill="{ACC}"', "hi": f' fill="{ACC_HI}"'}
    return "".join(f"<tspan{style[lv]}>{esc(t)}</tspan>" for lv, t in spans)


# --------------------------------------------------------------------------- header
def header(photo):
    W, H = 960, 440
    cols, cw, lh, fs = 46, 6.0, 10.5, 10
    rows = round(photo.height / photo.width * cols * cw / lh)
    aw, ah = cols * cw, rows * lh
    ax, ay = W - 32 - aw, 40 + (H - 40 - ah) / 2
    values = ink(photo, cols, rows)
    rnd = random.Random(7)

    defs, body = [], [window_chrome(W, H, "jailton@github: ~", "jsh · utf-8")]

    # Terminal (esquerda)
    x0 = 34
    lines = [
        ("type", 100, [("~$ ", ACC), ("whoami", TEXT)], 15, 0.5, MONO, None, None),
        ("wipe", 150, [("Jailton Santos", TEXT)], 42, 1.1, SANS, 700, 336),
        ("wipe", 182, [("desenvolvedor ", TEXT2), ("full-stack", ACC), (" · foco em back-end", MUTED)], 15, 1.55, MONO, None, None),
        ("type", 228, [("~$ ", ACC), ("cat stack.txt", TEXT)], 15, 2.2, MONO, None, None),
        ("wipe", 254, [("java · spring boot · python · fastapi · react · aws", ACC)], 15, 3.0, MONO, None, None),
        ("type", 300, [("~$ ", ACC), ("./status.sh", TEXT)], 15, 3.6, MONO, None, None),
        ("wipe", 326, [("  aberto a oportunidades: estágio / júnior", TEXT2)], 15, 4.3, MONO, None, None),
        ("type", 372, [("~$ ", ACC)], 15, 5.0, MONO, None, None),
    ]
    end = 0
    for mode, y, parts, size, begin, family, weight, width in lines:
        clip, el, end = typed(x0, y, parts, size, begin, mode=mode, family=family, weight=weight, width=width)
        defs.append(clip)
        body.append(el)
    # ponto pulsante do status + cursor final
    body.append(
        f'<circle cx="{x0 + 6}" cy="321" r="4.5" fill="{ACC}" opacity="0" filter="url(#glow)">'
        '<set attributeName="opacity" to="1" begin="4.3s" fill="freeze"/>'
        '<animate attributeName="r" values="4.5;7;4.5" dur="2s" begin="4.3s" repeatCount="indefinite"/></circle>'
    )
    body.append(cursor(x0 + 3 * 15 * CW + 2, 372, 15, end))

    # Retrato ASCII (direita) com decodificação linha a linha
    body.append(f'<rect x="{ax - 10}" y="{ay - 10}" width="{aw + 20}" height="{ah + 20}" fill="#010201" stroke="{LINE}"/>')
    for cx, cy, dx, dy in [(ax - 16, ay - 16, 1, 1), (ax + aw + 16, ay - 16, -1, 1), (ax - 16, ay + ah + 16, 1, -1), (ax + aw + 16, ay + ah + 16, -1, -1)]:
        body.append(f'<path d="M{cx} {cy + 14 * dy} V{cy} H{cx + 14 * dx}" fill="none" stroke="{ACC}" stroke-width="1.2"/>')
    ascii_rows, noise_rows = [], []
    for r in range(rows):
        y = ay + (r + 1) * lh - 2
        row = values[r * cols:(r + 1) * cols]
        delay = 0.3 + r * 0.06
        noise = "".join(rnd.choice(GLITCH) if v > 0.05 else NBSP for v in row)
        noise_rows.append(f'<text class="n" style="animation-delay:{delay:.2f}s" x="{ax}" y="{y:.1f}" font-size="{fs}" '
                          f'textLength="{aw}" lengthAdjust="spacingAndGlyphs" fill="{ACC}">{esc(noise)}</text>')
        ascii_rows.append(f'<text class="r" style="animation-delay:{delay + 0.16:.2f}s" x="{ax}" y="{y:.1f}" font-size="{fs}" '
                          f'textLength="{aw}" lengthAdjust="spacingAndGlyphs">{ascii_row_spans(row)}</text>')
    # caracteres que ficam "piscando" para sempre (glitch vivo)
    glitch = []
    dense = [i for i, v in enumerate(values) if v > 0.3]
    for k in range(18):
        i = rnd.choice(dense)
        gx, gy = ax + (i % cols) * cw, ay + (i // cols + 1) * lh - 2
        glitch.append(f'<text class="g" style="animation-delay:{2.4 + rnd.random() * 4:.2f}s;animation-duration:{2.5 + rnd.random() * 3:.2f}s" '
                      f'x="{gx:.1f}" y="{gy:.1f}" font-size="{fs}" fill="{ACC_HI}">{esc(rnd.choice(GLITCH))}</text>')

    # Lente que revela a foto real (foto embutida em base64, como no site)
    buf = io.BytesIO()
    small = photo.convert("RGB").resize((260, round(260 * photo.height / photo.width)), Image.LANCZOS)
    small.save(buf, "JPEG", quality=72)
    data = base64.b64encode(buf.getvalue()).decode()
    lens_r = 62
    pts = [(0.5 + math.sin(t * 1.3) * 0.17, 0.4 + math.sin(t * 2.1) * 0.1) for t in [k * math.tau / 12 for k in range(13)]]
    cxs = ";".join(f"{ax + aw * px:.1f}" for px, _ in pts)
    cys = ";".join(f"{ay + ah * py:.1f}" for _, py in pts)
    move = (f'<animate attributeName="cx" values="{cxs}" dur="12s" begin="2.6s" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{cys}" dur="12s" begin="2.6s" repeatCount="indefinite"/>')
    defs.append(
        '<radialGradient id="lensIn"><stop offset=".55" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="lensOut"><stop offset=".5" stop-color="#000"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>'
        f'<mask id="photoMask" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><circle cx="-300" cy="-300" r="{lens_r}" fill="url(#lensIn)">{move}</circle></mask>'
        f'<mask id="asciiMask" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#fff"/>'
        f'<circle cx="-300" cy="-300" r="{lens_r}" fill="url(#lensOut)">{move}</circle></mask>'
        f'<clipPath id="asciiBox"><rect x="{ax}" y="{ay}" width="{aw}" height="{ah}"/></clipPath>'
        f'<linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ACC}" stop-opacity="0"/>'
        f'<stop offset=".9" stop-color="{ACC}" stop-opacity=".14"/><stop offset="1" stop-color="{ACC}" stop-opacity="0"/></linearGradient>'
    )
    body.append(f'<g mask="url(#asciiMask)" filter="url(#glow)">{"".join(noise_rows)}{"".join(ascii_rows)}{"".join(glitch)}</g>')
    body.append(f'<image href="data:image/jpeg;base64,{data}" x="{ax}" y="{ay}" width="{aw}" height="{ah}" preserveAspectRatio="none" mask="url(#photoMask)"/>')
    body.append(f'<circle cx="-300" cy="-300" r="{lens_r}" fill="none" stroke="{ACC}" stroke-opacity=".55">{move}</circle>')
    body.append(f'<g clip-path="url(#asciiBox)"><rect class="beam" x="{ax}" y="{ay - 90}" width="{aw}" height="90" fill="url(#beam)"/></g>')
    body.append(f'<text x="{ax}" y="{ay - 18}" font-size="10" fill="{MUTED}">portrait.jpg</text>')
    body.append(f'<circle cx="{ax + aw - 64}" cy="{ay - 21.5}" r="3" fill="{RED}"><animate attributeName="opacity" values="1;0;1" '
                f'keyTimes="0;.5;1" calcMode="discrete" dur="1.4s" repeatCount="indefinite"/></circle>')
    body.append(f'<text x="{ax + aw}" y="{ay - 18}" text-anchor="end" font-size="10" fill="{ACC}">ascii · live</text>')
    body.append(f'<rect width="{W}" height="{H}" rx="12" fill="url(#scan)" opacity=".5"/>')

    css = f"""
.r {{ opacity: 0; animation: rin .5s ease-out forwards; }}
.n {{ opacity: 0; animation: noise .35s steps(2) forwards; }}
.g {{ opacity: 0; animation-name: flick; animation-iteration-count: infinite; animation-timing-function: steps(1); }}
.beam {{ animation: beam 5s linear 2.2s infinite; }}
@keyframes rin {{ to {{ opacity: 1; }} }}
@keyframes noise {{ 0% {{ opacity: 0; }} 30% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}
@keyframes flick {{ 0%, 86% {{ opacity: 0; }} 88%, 96% {{ opacity: 1; }} }}
@keyframes beam {{ from {{ transform: translateY(0); }} to {{ transform: translateY({ah + 90}px); }} }}
"""
    label = "Terminal: whoami, Jailton Santos, desenvolvedor full-stack com foco em back-end; ao lado, retrato em ASCII"
    return svg_doc(W, H, "\n".join(body), css=css, defs="".join(defs), label=label)


# --------------------------------------------------------------------------- pequenos componentes
def section_title(index, command, label):
    W, H, size = 960, 56, 17
    defs, body = [], []
    body.append(f'<text x="2" y="35" font-size="13" font-weight="700" fill="{ACC}">{index}</text>')
    clip, el, end = typed(36, 35, [("$ ", ACC), (command, TEXT)], size, 0.25)
    defs.append(clip)
    body.append(el)
    after = 36 + (len(command) + 2) * size * CW
    body.append(cursor(after + 4, 35, size, end))
    start = after + 28
    length = W - start - 2
    defs.append(f'<linearGradient id="rule" x1="0" x2="1"><stop offset="0" stop-color="{LINE2}"/><stop offset="1" stop-color="{LINE2}" stop-opacity="0"/></linearGradient>')
    body.append(f'<path d="M{start:.1f} 30 H{W - 2}" stroke="url(#rule)" stroke-width="1" stroke-dasharray="{length:.1f}" stroke-dashoffset="{length:.1f}">'
                f'<animate attributeName="stroke-dashoffset" to="0" dur="1.2s" begin="{end:.2f}s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.65 0 0.35 1"/></path>')
    return svg_doc(W, H, "\n".join(body), defs="".join(defs), label=label)


def window_bar(path, status, label):
    W, H = 960, 46
    body = [
        f'<path d="M12.5 0.5 H{W - 12.5} A12 12 0 0 1 {W - 0.5} 12.5 V{H} H0.5 V12.5 A12 12 0 0 1 12.5 0.5 Z" fill="{BAR}" stroke="{LINE}"/>',
        f'<circle cx="24" cy="23" r="5.5" fill="{RED}"/><circle cx="42" cy="23" r="5.5" fill="{AMBER}"/><circle cx="60" cy="23" r="5.5" fill="{GREEN_DOT}"/>',
        f'<text x="84" y="27.5" font-size="13" fill="{TEXT2}">{esc(path)}</text>',
        f'<circle cx="{W - 24 - len(status) * 7.2 - 14}" cy="23" r="4" fill="{ACC}" filter="url(#glow)">'
        '<animate attributeName="opacity" values="1;.25;1" dur="2s" repeatCount="indefinite"/></circle>',
        f'<text x="{W - 24}" y="27.5" text-anchor="end" font-size="12" fill="{ACC}">{esc(status)}</text>',
        f'<rect class="sweep" x="-220" y="{H - 1.5}" width="220" height="1.5" fill="url(#sweep)"/>',
    ]
    defs = (f'<linearGradient id="sweep"><stop offset="0" stop-color="{ACC}" stop-opacity="0"/><stop offset=".5" stop-color="{ACC}"/>'
            f'<stop offset="1" stop-color="{ACC}" stop-opacity="0"/></linearGradient>')
    css = f".sweep {{ animation: sweep 4.5s linear infinite; }} @keyframes sweep {{ to {{ transform: translateX({W + 220}px); }} }}"
    return svg_doc(W, H, "\n".join(body), css=css, defs=defs, label=label)


def stack_tree(groups):
    W, size, lh = 960, 14, 32
    H = 30 + lh * (len(groups) + 1) + 10
    body = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{PANEL}" stroke="{LINE}"/>']
    body.append(f'<rect class="hl" x="12" y="{30 - 22}" width="{W - 24}" height="{lh - 4}" rx="6" fill="{ACC}" opacity=".06"/>')
    body.append(f'<text class="row" style="animation-delay:.2s" x="32" y="{30 + 4}" font-size="{size}" fill="{ACC}">~/stack</text>')
    for i, (group, items) in enumerate(groups):
        y = 30 + lh * (i + 1) + 4
        branch = "└── " if i == len(groups) - 1 else "├── "
        line = [(branch, DIM), (f"{group}/".ljust(18), ACC), (items, TEXT2)]
        text = "".join(t for t, _ in line)
        spans = "".join(f'<tspan fill="{c}">{esc(t.replace(" ", NBSP))}</tspan>' for t, c in line)
        body.append(f'<text class="row" style="animation-delay:{0.45 + i * 0.18:.2f}s" x="32" y="{y}" font-size="{size}" '
                    f'textLength="{len(text) * size * CW:.1f}" lengthAdjust="spacingAndGlyphs">{spans}</text>')
    css = f"""
.row {{ opacity: 0; animation: rowin .6s cubic-bezier(.16,1,.3,1) forwards; }}
.hl {{ animation: hl {len(groups) * 1.1 + 1.1:.1f}s steps({len(groups) + 1}) 1.8s infinite; }}
@keyframes rowin {{ from {{ opacity: 0; transform: translateX(-10px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes hl {{ from {{ transform: translateY(0); }} to {{ transform: translateY({lh * (len(groups) + 1)}px); }} }}
"""
    return svg_doc(W, H, "\n".join(body), css=css, label="tree ~/stack: " + "; ".join(f"{g}: {it}" for g, it in groups))


def divider():
    W, H = 960, 24
    defs = (f'<linearGradient id="seg"><stop offset="0" stop-color="{ACC}" stop-opacity="0"/><stop offset=".5" stop-color="{ACC}"/>'
            f'<stop offset="1" stop-color="{ACC}" stop-opacity="0"/></linearGradient>')
    body = (f'<path d="M0 12 H{W}" stroke="{LINE}"/><rect class="seg" x="-240" y="11" width="240" height="2" fill="url(#seg)"/>'
            f'<rect x="{W / 2 - 4}" y="8" width="8" height="8" fill="{BG}" stroke="{ACC}" transform="rotate(45 {W / 2} 12)"/>')
    css = f".seg {{ animation: seg 5s cubic-bezier(.65,0,.35,1) infinite; }} @keyframes seg {{ to {{ transform: translateX({W + 240}px); }} }}"
    return svg_doc(W, H, body, css=css, defs=defs, label="divisor")


STACK = [
    ("linguagens", "java 21 · python 3.13 · typescript · sql"),
    ("back-end", "spring boot · spring security (jwt) · jpa / hibernate · fastapi · pydantic v2"),
    ("dados", "postgresql · mysql · dynamodb · caffeine · hikaricp · flyway"),
    ("cloud-devops", "aws lambda · s3 + cloudfront · docker · render · neon · vercel · github actions"),
    ("front-end", "react 19 · typescript · tailwind 4 · vite · tanstack query · gsap · webgl"),
]

TITLES = {
    "sobre": ("01", "cat sobre.md", "Sobre mim"),
    "stack": ("02", "tree ~/stack", "Stack"),
    "projetos": ("03", "ls ~/projetos", "Projetos em destaque"),
    "outros": ("04", "ls ~/projetos/outros", "Outros projetos"),
    "numeros": ("05", "git log --stat", "GitHub em números"),
    "contato": ("06", "./contato.sh", "Contato"),
}

WINDOWS = {
    "portfolio": ("~/projetos/portfolio", "online", "Janela: portfólio online"),
    "myworld": ("~/projetos/myworld", "online", "Janela: MyWorld online"),
    "brasilpanel": ("~/projetos/brasilpanel", "em produção", "Janela: Brasil Panel em produção"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", required=True, help="foto para o retrato ASCII do cabeçalho")
    args = parser.parse_args()
    ASSETS.mkdir(exist_ok=True)
    outputs = {"header.svg": header(Image.open(args.photo)), "stack.svg": stack_tree(STACK), "divider.svg": divider()}
    for key, (idx, cmd, label) in TITLES.items():
        outputs[f"title-{key}.svg"] = section_title(idx, cmd, label)
    for key, (path, status, label) in WINDOWS.items():
        outputs[f"window-{key}.svg"] = window_bar(path, status, label)
    for name, content in outputs.items():
        (ASSETS / name).write_text(content, encoding="utf-8")
        print(f"assets/{name}: {len(content.encode()) // 1024} KB")


if __name__ == "__main__":
    main()
