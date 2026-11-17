"""Redraw the deck's chart images from private/deck_stats.json, at the same pixel size as the images in the deck.

    python3 deck_charts.py [out_dir]          # default: ../private/charts

Needs matplotlib (work/deps) and the deck font in work/fonts (Calibri, never committed). Each PNG is named
after its slide, so it can be swapped in with Google Slides' "Replace image" without moving anything.
"""
import json, os, sys
from common import DATA, PRIVATE, CLASSES
sys.path.insert(0, os.path.join(DATA, 'deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D

for f in ('DeckCalibri-Regular.ttf', 'DeckCalibri-Bold.ttf'):
    font_manager.fontManager.addfont(os.path.join(DATA, 'fonts', f))
plt.rcParams.update({'font.family': 'DeckCalibri', 'axes.unicode_minus': False})

F = json.load(open(os.path.join(PRIVATE, 'deck_stats.json')))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PRIVATE, 'charts')
os.makedirs(OUT, exist_ok=True)
INK, MUTE, GRID, POOL, AXIS = '#241712', '#5F5047', '#E3DAD3', '#B7AAA1', '#B7AAA1'
COL = dict(zip([c['name'] for c in CLASSES], ['#00918C', '#7350B5', '#C2571A']))
cl = [c['name'] for c in CLASSES]
latest = cl[-1]
FS = 35  # points at dpi 100: about 49 px, the size of the labels in the deck's images


def fig(w, h):
    f = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    f.patch.set_facecolor('white')
    return f


def plain(ax, grid_y=False, left=False):
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.spines['left'].set_visible(left)
    ax.spines['left'].set_color(AXIS); ax.spines['left'].set_linewidth(2)
    ax.spines['bottom'].set_color(AXIS); ax.spines['bottom'].set_linewidth(2.5)
    ax.tick_params(length=0, labelsize=FS, labelcolor=MUTE, pad=12)
    if grid_y:
        ax.yaxis.grid(True, color=GRID, linewidth=2.2); ax.set_axisbelow(True)


def line_legend(f, names, colors, y=0.975):
    hs = [Line2D([0], [0], color=c, lw=4, ls=(0, (1.2, 0.8)), marker='o', ms=12, mec='white', mew=0) for c in colors]
    f.legend(hs, names, loc='upper center', bbox_to_anchor=(0.5, y), ncol=len(names), frameon=False, fontsize=FS + 2,
             handlelength=1.1, handletextpad=0.5, columnspacing=1.4, labelcolor=INK)


def line(ax, xs, ys, c):
    ax.plot(xs, ys, color=c, lw=5.5, marker='o', ms=21, mfc=c, mec='white', mew=2.5, solid_capstyle='round', zorder=3)


def save(f, name):
    p = os.path.join(OUT, name)
    f.savefig(p, dpi=100, facecolor='white')
    plt.close(f)
    print('wrote', p)


# slide 8: same-gender share by chat number
f = fig(2047, 1270); ax = f.add_axes([0.072, 0.075, 0.905, 0.80])
cats = ['Chats 1-10', 'Chats 11-20', 'Chats 21-30', 'Chats 31+']
MIN_N = 20  # same rule as the original: a point needs enough chats behind it
for c in cl:
    ys = F['s8_fade_by_class'][c]
    ns = F.get('s8_fade_n', {}).get(c, [MIN_N] * 4)
    pts = [(i, y) for i, (y, n) in enumerate(zip(ys, ns)) if y is not None and n >= MIN_N]
    line(ax, [p[0] for p in pts], [round(p[1]) for p in pts], COL[c])
line(ax, range(4), [round(v) for v in F['s8_pool']], POOL)
ax.set_ylim(30, 80); ax.set_yticks(range(30, 81, 10)); ax.set_yticklabels([f'{v}%' for v in range(30, 81, 10)])
ax.set_xlim(-0.5, 3.5); ax.set_xticks(range(4)); ax.set_xticklabels(cats)
plain(ax, grid_y=True)
line_legend(f, cl + ['Same-gender share of who is left'], [COL[c] for c in cl] + [POOL])
save(f, 'slide08_gender_fade.png')

# slide 9: actual vs random
f = fig(2047, 1387); ax = f.add_axes([0.225, 0.03, 0.70, 0.87])
g, m = F['s9_gender'], F['s9_major']
rows = [('Same gender', g), ('Same major group', m)]
for i, (lab, d) in enumerate(rows):
    y = 1 - i
    ax.barh(y + 0.2, d['random'], height=0.4, color=POOL)
    ax.barh(y - 0.2, d['actual'], height=0.4, color=COL[cl[1]])
    for yy, v in ((y + 0.2, d['random']), (y - 0.2, d['actual'])):
        ax.text(v + 0.5, yy, f'{v:.1f}%', va='center', ha='left', fontsize=FS + 2, color=INK)
plain(ax, left=True); ax.spines['bottom'].set_visible(False)
ax.set_yticks([1, 0]); ax.set_yticklabels([r[0] for r in rows], fontsize=FS + 2)
ax.set_ylim(-0.55, 1.55); ax.set_xlim(0, 72); ax.set_xticks([])
f.legend([plt.Rectangle((0, 0), 1, 1, color=POOL), plt.Rectangle((0, 0), 1, 1, color=COL[cl[1]])],
         ['If chats were random', 'What actually happened'], loc='upper center', bbox_to_anchor=(0.35, 1.0), ncol=2,
         frameon=False, fontsize=FS + 2, handlelength=0.7, handleheight=0.7, labelcolor=INK)
save(f, 'slide09_gender_major.png')


def hbars(name, items, color, size, left, xmax):
    f = fig(*size); ax = f.add_axes([left, 0.015, 0.97 - left - 0.04, 0.97])
    n = len(items)
    for i, (lab, v) in enumerate(items):
        ax.barh(n - 1 - i, v, height=0.72, color=color)
        ax.text(v + xmax * 0.004, n - 1 - i, str(v), va='center', ha='left', fontsize=FS, color=INK)
    ax.set_yticks(range(n)); ax.set_yticklabels([lab for lab, _ in items][::-1], fontsize=FS)
    ax.set_ylim(-0.6, n - 0.4); ax.set_xlim(0, xmax); ax.set_xticks([])
    plain(ax, left=True); ax.spines['bottom'].set_visible(False)
    ax.tick_params(axis='y', pad=22)
    save(f, name)


# slide 10: distinct new members met
top = F['s10_most_met'][:10]
hbars('slide10_most_met.png', [(b, n) for b, n in top], COL[cl[0]], (2046, 1285), 0.2, top[0][1] * 1.07)

# slide 14: exclamation points by week, break weeks skipped
f = fig(2047, 1270); ax = f.add_axes([0.072, 0.075, 0.905, 0.80])
weeks = 7
for c in cl:
    ys = [p[1] for p in F['s14_exclaim_by_week'][c]][:weeks]
    line(ax, range(len(ys)), ys, COL[c])
ax.set_ylim(0, 100); ax.set_yticks(range(0, 101, 20)); ax.set_yticklabels([f'{v}%' for v in range(0, 101, 20)])
ax.set_xlim(-0.5, weeks - 0.5); ax.set_xticks(range(weeks)); ax.set_xticklabels([f'Week {i + 1}' for i in range(weeks)])
plain(ax, grid_y=True)
line_legend(f, cl, [COL[c] for c in cl])
save(f, 'slide14_exclamation.png')

# slide 15: what the emails mention
items = sorted(F['s15_mentions'].items(), key=lambda kv: -kv[1])
hbars('slide15_mentions.png', items, COL[latest], (2046, 1285), 0.18, items[0][1] * 1.07)

# slide 16: brothers met per new member, by week
wk = F['s16_weeks_shown']
f = fig(2046, 1334); ax = f.add_axes([0.062, 0.075, 0.915, 0.80])
for c in cl:
    line(ax, range(wk), F['s16_met_by_week'][c][:wk], COL[c])
top_y = 5 * (int(max(max(F['s16_met_by_week'][c][:wk]) for c in cl)) // 5 + 1)
ax.set_ylim(0, top_y); ax.set_yticks(range(0, top_y + 1, 5))
ax.set_xlim(-0.5, wk - 0.5); ax.set_xticks(range(wk)); ax.set_xticklabels([f'Week {i + 1}' for i in range(wk)])
plain(ax, grid_y=True)
line_legend(f, cl, [COL[c] for c in cl])
save(f, 'slide16_pace.png')

# slide 17: latest-class chats per brother, by class
rows = F['s17_per_brother_by_class']
f = fig(1770, 1545); ax = f.add_axes([0.03, 0.085, 0.94, 0.78])
for i, (k, v, _) in enumerate(rows):
    ax.bar(i, v, width=0.68, color=COL[latest])
    ax.text(i, v + rows[0][1] * 0.012, f'{v:.1f}', ha='center', va='bottom', fontsize=FS + 13, color=INK)
plain(ax)
ax.set_xticks(range(len(rows))); ax.set_xticklabels([r[0] for r in rows], fontsize=FS + 13)
ax.set_ylim(0, rows[0][1] * 1.0); ax.set_yticks([]); ax.set_xlim(-0.55, len(rows) - 0.45)
f.text(0.5, 0.965, f'{latest} chats per brother, by class', ha='center', va='top', fontsize=FS + 15, color=INK)
save(f, 'slide17_per_class.png')

# slide 18: brothers by number of latest-class chats
h = dict(F['s18_histogram'])
xs = list(range(0, max(h) + 1))
f = fig(2047, 1270); ax = f.add_axes([0.01, 0.15, 0.98, 0.84])
for x in xs:
    if h.get(x):
        ax.bar(x, h[x], width=0.78, color=COL[latest])
        ax.text(x, h[x] + max(h.values()) * 0.012, str(h[x]), ha='center', va='bottom', fontsize=FS, color=INK)
ax.set_xticks(xs); ax.set_xticklabels([str(x) for x in xs], fontsize=FS)
ax.set_ylim(0, max(h.values()) * 1.1); ax.set_yticks([]); ax.set_xlim(-0.6, xs[-1] + 0.6)
plain(ax)
f.text(0.5, 0.01, f'{latest} chats received', ha='center', va='bottom', fontsize=FS, color=MUTE)
save(f, 'slide18_histogram.png')
