"""Render a blue/white README calendar using real GitHub contribution data."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request
from xml.sax.saxutils import escape

COLORS = ['#142033', '#23436b', '#367cc0', '#84caff', '#e8f6ff']
LEVELS = ['NONE', 'FIRST_QUARTILE', 'SECOND_QUARTILE', 'THIRD_QUARTILE', 'FOURTH_QUARTILE']
MONTHS = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def fetch_calendar(user, token):
    end = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    start = end - dt.timedelta(days=365)
    query = '''query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date weekday contributionCount contributionLevel } }
          }
        }
      }
    }'''
    body = json.dumps({'query': query, 'variables': {
        'login': user, 'from': start.isoformat(), 'to': end.isoformat()
    }}).encode()
    req = urllib.request.Request('https://api.github.com/graphql', data=body, headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
        'User-Agent': 'profile-contribution-calendar'
    })
    with urllib.request.urlopen(req, timeout=45) as response:
        payload = json.load(response)
    if payload.get('errors'):
        raise RuntimeError('GitHub rejected the calendar query: ' + str(payload['errors']))
    return payload['data']['user']['contributionsCollection']['contributionCalendar']


def render(calendar, user):
    weeks = calendar['weeks']
    days = [day for week in weeks for day in week['contributionDays']]
    if not 360 <= len(days) <= 367 or not 52 <= len(weeks) <= 54:
        raise ValueError('Incomplete calendar; keeping the existing image')
    dates = [dt.date.fromisoformat(d['date']) for d in days]
    if len(set(dates)) != len(dates) or max(dates) - min(dates) != dt.timedelta(days=len(days)-1):
        raise ValueError('Calendar dates are duplicated or missing')
    for d, date in zip(days, dates):
        if type(d['contributionCount']) is not int or d['contributionCount'] < 0:
            raise ValueError('Invalid contribution count')
        if d['contributionLevel'] not in LEVELS or d['weekday'] != (date.weekday()+1) % 7:
            raise ValueError('Invalid contribution day')
    total = calendar['totalContributions']
    if sum(d['contributionCount'] for d in days) != total:
        raise ValueError('Calendar total does not match daily counts')
    chunks = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="290" viewBox="0 0 900 290" role="img" aria-labelledby="title desc">',
        '<title id="title">Calendário de contribuições de ' + escape(user) + '</title>',
        '<desc id="desc">' + str(total) + ' contribuições reais entre ' + str(min(dates)) + ' e ' + str(max(dates)) + '. Tons de azul e branco indicam a intensidade.</desc>',
        '<defs><radialGradient id="glow"><stop stop-color="#3153bd" stop-opacity=".18"/><stop offset="1" stop-color="#3153bd" stop-opacity="0"/></radialGradient><clipPath id="clip"><rect width="900" height="290" rx="20"/></clipPath></defs>',
        '<rect x=".5" y=".5" width="899" height="289" rx="20" fill="#090d16" stroke="#242838"/>',
        '<g clip-path="url(#clip)"><ellipse cx="660" cy="180" rx="340" ry="160" fill="url(#glow)"/></g>',
        '<g font-family="Segoe UI,Arial,sans-serif">',
        '<text x="36" y="37" font-size="11" font-weight="600" letter-spacing="3" fill="#86a0bc">03 / ATIVIDADE NO GITHUB</text>',
        '<text x="36" y="73" font-size="25" font-weight="600" fill="#edf1fa">Código em movimento.</text>',
        f'<text x="864" y="72" text-anchor="end" font-size="14" fill="#a9c9ed">{total} contribuições no período</text>',
    ]
    seen = set()
    for w, week in enumerate(weeks):
        for d in week['contributionDays']:
            date = dt.date.fromisoformat(d['date'])
            key = (date.year, date.month)
            if key not in seen:
                if not seen or date.day <= 7:
                    # Skip a last partial month if it would overlap its neighbor.
                    if not seen or w < len(weeks)-2:
                        chunks.append(f'<text x="{58+w*15}" y="99" font-size="11" fill="#90a1bc">{MONTHS[date.month]}</text>')
                seen.add(key)
            color = COLORS[LEVELS.index(d['contributionLevel'])]
            chunks.append(f'<rect x="{58+w*15}" y="{110+d["weekday"]*15}" width="12" height="12" rx="2.5" fill="{color}"><title>{d["date"]}: {d["contributionCount"]} contribuições</title></rect>')
    for weekday, label in [(1, 'Seg'), (3, 'Qua'), (5, 'Sex')]:
        chunks.append(f'<text x="20" y="{120+weekday*15}" font-size="10" fill="#90a1bc">{label}</text>')
    begin, end = min(dates).strftime('%d/%m/%Y'), max(dates).strftime('%d/%m/%Y')
    chunks.append(f'<text x="36" y="251" font-size="12" fill="#90a1bc">{begin} — {end}</text>')
    chunks.append('<text x="682" y="251" font-size="11" fill="#90a1bc">Menos</text>')
    for i, color in enumerate(COLORS):
        chunks.append(f'<rect x="{724+i*17}" y="240" width="12" height="12" rx="2.5" fill="{color}"/>')
    chunks.append('<text x="817" y="251" font-size="11" fill="#90a1bc">Mais</text></g></svg>')
    return ''.join(chunks)


def main():
    user = os.environ['PROFILE_USER']
    calendar = fetch_calendar(user, os.environ['GH_TOKEN'])
    svg = render(calendar, user)
    target = Path('assets/readme/04-atividade.svg')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding='utf-8')
    print('Updated contribution calendar:', calendar['totalContributions'], 'contributions')


if __name__ == '__main__':
    main()
