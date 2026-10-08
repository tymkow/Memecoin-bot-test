# Ile jego wyboru tłumaczy rynek - 08.10.2026 17:48

Tokeny pump.fun utworzone, gdy był aktywny (+-5 min od jego transakcji): 42812 w 37 godzinach aktywności. Wszedł w ciągu 60 s od utworzenia w 97 z nich (0.23%, ~2.6/h).


## Wiek 5 s (tokenów z danymi 33648, w tym jego 83)

| reguła | tokenów spełnia | na godzinę | z tego jego | trafność (kupił) | pokrycie (jego wejścia spełniały) |
|---|---|---|---|---|---|
| portfele >= 8 | 5857 | 158.3 | 72 | 1% | 87% |
| portfele >= 15 | 3157 | 85.3 | 59 | 2% | 71% |
| portfele >= 25 | 1594 | 43.1 | 49 | 3% | 59% |
| portfele >= 15 i kupno 10 s > 3 SOL | 3154 | 85.2 | 59 | 2% | 71% |
| portfele >= 25 i kupno 10 s > 6 SOL | 1589 | 42.9 | 49 | 3% | 59% |
| slot startu > 3 SOL i portfele >= 15 | 2856 | 77.2 | 55 | 2% | 66% |
| portfele >= 40 | 596 | 16.1 | 25 | 4% | 30% |

## Wiek 10 s (tokenów z danymi 33716, w tym jego 83)

| reguła | tokenów spełnia | na godzinę | z tego jego | trafność (kupił) | pokrycie (jego wejścia spełniały) |
|---|---|---|---|---|---|
| portfele >= 8 | 6731 | 181.9 | 79 | 1% | 95% |
| portfele >= 15 | 4012 | 108.4 | 71 | 2% | 86% |
| portfele >= 25 | 2474 | 66.9 | 59 | 2% | 71% |
| portfele >= 15 i kupno 10 s > 3 SOL | 4006 | 108.3 | 71 | 2% | 86% |
| portfele >= 25 i kupno 10 s > 6 SOL | 2469 | 66.7 | 59 | 2% | 71% |
| slot startu > 3 SOL i portfele >= 15 | 3538 | 95.6 | 66 | 2% | 80% |
| portfele >= 40 | 1345 | 36.4 | 52 | 4% | 63% |

## Wiek 15 s (tokenów z danymi 33765, w tym jego 83)

| reguła | tokenów spełnia | na godzinę | z tego jego | trafność (kupił) | pokrycie (jego wejścia spełniały) |
|---|---|---|---|---|---|
| portfele >= 8 | 7110 | 192.2 | 80 | 1% | 96% |
| portfele >= 15 | 4350 | 117.6 | 75 | 2% | 90% |
| portfele >= 25 | 2803 | 75.8 | 69 | 2% | 83% |
| portfele >= 15 i kupno 10 s > 3 SOL | 2723 | 73.6 | 65 | 2% | 78% |
| portfele >= 25 i kupno 10 s > 6 SOL | 1810 | 48.9 | 59 | 3% | 71% |
| slot startu > 3 SOL i portfele >= 15 | 3788 | 102.4 | 70 | 2% | 84% |
| portfele >= 40 | 1679 | 45.4 | 56 | 3% | 67% |

## Poza rynkiem: tokeny z tłumem (portfele >= 15 w wieku 10 s) - kupione przez niego vs pominięte

Kupione 91, pominięte 3921.

| źródło grafiki (narzędzie startu) | kupione | pominięte |
|---|---|---|
| Axiom | 26% | 18% |
| brak | 0% | 0% |
| inne | 24% | 23% |
| pump.fun (strona) | 35% | 45% |
| z X (tweet -> coin) | 14% | 14% |

| cecha | kupione (mediana) | pominięte (mediana) | AUC |
|---|---|---|---|
| twórca: wcześniejsze starty | 0 | 0 | 0.54 |
| twórca: wcześniejsze zmigrowane | 0 | 0 | 0.52 |
| długość nazwy | 8 | 9 | 0.43 |
| portfele w wieku A | 54 | 29 | 0.74 |
| kupno SOL 10 s | 51.4 | 23 | 0.79 |
| SOL w slocie startu | 10.6 | 9.86 | 0.55 |
| twórca kupił SOL | 0.988 | 0.988 | 0.52 |
| zmiana ceny od startu | nan | nan | 0.50 |

## Ranking w chwili wejścia (najmocniejszy wynik)

Dla każdego jego wczesnego wejścia (<= 60 s od startu, N 84): wszystkie tokeny utworzone w ostatnich 2 min przed jego
zakupem (mediana 47), uszeregowane po kwocie zakupów w ostatnich 10 s (cechy tylko sprzed jego transakcji).
Jego token był **nr 1 w 55%** przypadków, w top 3 w 81%, w top 5 w 92% (mediana miejsca: 1).
Wniosek: kupuje NAJGORĘTSZY start chwili (największy napływ kupujących i SOL w ostatnich sekundach) - tak, jak
wygląda lista nowych tokenów w terminalu (np. Axiom) posortowana po wolumenie. Źródło startu z X nie odróżnia jego
wyborów od pominiętych gorących startów (14% vs 14%); historia twórcy też nie (AUC 0.52-0.54).
