## Wzorce wykresu użytkownika (prosta / schodki / zygzak / V) - na wyniku po kosztach

Progi USTALONE Z OPISU, przed spojrzeniem na wyniki:
  prosta    log ceny ~ czas w oknie [migracja, T]: R^2 >= 0,85 i nachylenie > 0 ("prosta linia do góry")
  schodki   >= 4 minuty z +3% lub więcej, wielkość tych wzrostów podobna (CV < 0,5), żaden zjazd minutowy < -5%
  zygzak    wśród ruchów minutowych |r| > 1%: >= 60% zmian kierunku
  V         od szczytu spadek >= 40%, potem w T cena >= 1,5 x dołek ("mocno spadło, potem pompa = kolejny dump")
Każdy wzorzec jako filtr "NIE kupuj, gdy wzorzec" (hipoteza: to rugi) i odwrotnie; eksploracja 70% / TEST 30%.



| wzorzec | zbiór | N z wzorcem (udział) | wynik z wzorcem | wynik bez wzorca | S6 z wzorcem | rug (e) z / bez |
|---|---|---|---|---|---|---|
| prosta linia do góry | eksploracja | 75 (17%) | -33.4% | -12.1% | -31.5% | 40% / 20% |
| prosta linia do góry | TEST | 40 (22%) | -16.8% | -15.5% | -18.2% | 22% / 24% |
| prosta linia do góry | Twoje oceny | 36 | 'nie kupić' 100% |  |  |  |
| schodki | eksploracja | 45 (10%) | -40.2% | -13.0% | -40.6% | 40% / 21% |
| schodki | TEST | 30 (16%) | -25.1% | -13.9% | -25.9% | 27% / 23% |
| schodki | Twoje oceny | 18 | 'nie kupić' 100% |  |  |  |
| zygzak | eksploracja | 52 (12%) | -11.9% | -16.4% | -12.4% | 25% / 23% |
| zygzak | TEST | 19 ⚠️ niewiarygodny (10%) | +0.3% | -17.6% | +6.4% | 32% / 23% |
| zygzak | Twoje oceny | 21 | 'nie kupić' 81% |  |  |  |
| spadek, potem pompa (V) | eksploracja | 52 (12%) | -17.6% | -15.6% | -14.6% | 42% / 21% |
| spadek, potem pompa (V) | TEST | 24 ⚠️ niewiarygodny (13%) | -26.9% | -14.1% | -19.6% | 33% / 22% |
| spadek, potem pompa (V) | Twoje oceny | 24 | 'nie kupić' 50% |  |  |  |

**Filtry "nie kupuj, gdy wzorzec" (vs baseline i oczekiwany random_eligible na TEŚCIE):**

| filtr / hipoteza | eksploracja: filtr vs baseline (N) | TEST: filtr vs baseline (N; p losowe) | random_eligible oczekiwany, TEST (N) | werdykt |
|---|---|---|---|---|
| wzorzec prosta: nie kupuj (S0) | -12.1% vs -15.8% (N 356/431) | -15.5% vs -15.7% (N 146/186; p 0.43) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec prosta: kupuj TYLKO z nim (S0) | -33.4% vs -15.8% (N 75/431) | -16.8% vs -15.7% (N 40/186; p 0.56) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec prosta: nie kupuj (S6) | -11.9% vs -15.3% (N 356/431) | -12.2% vs -13.5% (N 146/186; p 0.19) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec prosta: kupuj TYLKO z nim (S6) | -31.5% vs -15.3% (N 75/431) | -18.2% vs -13.5% (N 40/186; p 0.80) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec schodki: nie kupuj (S0) | -13.0% vs -15.8% (N 386/431) | -13.9% vs -15.7% (N 156/186; p 0.11) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec schodki: kupuj TYLKO z nim (S0) | -40.2% vs -15.8% (N 45/431) | -25.1% vs -15.7% (N 30/186; p 0.89) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec schodki: nie kupuj (S6) | -12.4% vs -15.3% (N 386/431) | -11.1% vs -13.5% (N 156/186; p 0.03) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec schodki: kupuj TYLKO z nim (S6) | -40.6% vs -15.3% (N 45/431) | -25.9% vs -13.5% (N 30/186; p 0.96) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec zygzak: nie kupuj (S0) | -16.4% vs -15.8% (N 379/431) | -17.6% vs -15.7% (N 167/186; p 0.95) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec zygzak: kupuj TYLKO z nim (S0) | -11.9% vs -15.8% (N 52/431) | +0.3% vs -15.7% (N 19 ⚠️ niewiarygodny/186; p 0.05) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec zygzak: nie kupuj (S6) | -15.7% vs -15.3% (N 379/431) | -15.8% vs -13.5% (N 167/186; p 0.99) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec zygzak: kupuj TYLKO z nim (S6) | -12.4% vs -15.3% (N 52/431) | +6.4% vs -13.5% (N 19 ⚠️ niewiarygodny/186; p 0.01) | +6.3% (N 23 ⚠️ niewiarygodny) | kierunek OK, niepewne (N 19, p 0.01) |
| wzorzec V: nie kupuj (S0) | -15.6% vs -15.8% (N 379/431) | -14.1% vs -15.7% (N 162/186; p 0.09) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec V: kupuj TYLKO z nim (S0) | -17.6% vs -15.8% (N 52/431) | -26.9% vs -15.7% (N 24 ⚠️ niewiarygodny/186; p 0.90) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec V: nie kupuj (S6) | -15.4% vs -15.3% (N 379/431) | -12.6% vs -13.5% (N 162/186; p 0.21) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec V: kupuj TYLKO z nim (S6) | -14.6% vs -15.3% (N 52/431) | -19.6% vs -13.5% (N 24 ⚠️ niewiarygodny/186; p 0.78) | +6.3% (N 23 ⚠️ niewiarygodny) | NIE trzyma się na teście |