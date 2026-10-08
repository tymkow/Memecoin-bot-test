# Arbitraż między pulami DEX (paper) - stan 07.10.2026 19:33

Pomiar: 3.4 h pracy skanera. Tokenów sprawdzonych 495, z >= 2 pulami token/SOL (płynność >= $1000): 35 (7%).

## Przesiew (różnica cen wg DexScreenera)

| powód | par | mediana różnicy bps | p90 bps |
|---|---|---|---|
| poniżej progu | 2283 | 16 | 41 |
| różnica >= próg | 256 | 205 | 34085 |
| różnica >= próg, nie najlepsza para | 1229 | 98 | 205 |
| ten sam DEX (kwotowanie nie rozdzieli pul) | 1114 | 45 | 200 |
| próbka losowa (kontrola przesiewu) | 3 | 46 | 47 |

## Weryfikacja kwotowaniami Jupitera (pierwsze kwotowanie, bez ponownych)

| kwota SOL | kwotowań | brutto > 0 | netto > 0 (min. koszty) | netto > 0 (napiwek 50%) | mediana brutto % | max netto SOL |
|---|---|---|---|---|---|---|
| 0.1 | 426 | 4 | 4 | 4 | -1.09% | +0.00333 |
| 0.5 | 4 | 0 | 0 | 0 | -4.24% | -0.01493 |
| 2.0 | 4 | 0 | 0 | 0 | -5.12% | -0.07763 |

Statusy kwotowań: {'error': 1, 'noroute': 89, 'ok': 438} (noroute = Jupiter nie ma bezpośredniej trasy przez ten DEX).

Ponowne kwotowanie po 10 s: 4 okazji, nadal zyskownych 0.

**Górna granica zysku** (każda okazja wzięta przez nas, bez konkurencji, min. koszty): 0.0044 SOL z 4 okazji = 0.0310 SOL/dobę. Konkurencyjne boty (Jito, ms) zabierają większość z nich - realnie mniej.
