## 1b. First buyers - klasteryzacja (KMeans / DBSCAN)

Portfeli (portfel x token): 3731 (eksploracja 2490, TEST 1241); cech: 13.

silhouette (eksploracja): k=2: 0.270, k=3: 0.271, k=4: 0.281, k=5: 0.259, k=6: 0.264, k=7: 0.270 -> **k=4**

**Skład klastrów KMeans wg grup regułowych** (czy klasteryzacja odtwarza reguły?):

| klaster | N | insider | sniper | smart | retail | śr. wiek (h) | sprzedał w 5 min | śr. zakup SOL |
|---|---|---|---|---|---|---|---|---|---|
| K0 | 1145 | 41% | 19% | 0% | 40% | 170 | 53% | 3.50 |
| K1 | 2189 | 20% | 79% | 0% | 1% | 956 | 76% | 1.16 |
| K2 | 213 | 100% | 0% | 0% | 0% | 1 | 11% | 41.66 |
| K3 | 184 | 100% | 0% | 0% | 0% | 21 | 70% | 2.09 |

DBSCAN (eps=1.57, min 10, próbka 2490 portfeli eksploracji): klastrów 12, szum 11%, największy klaster 31% - są wyraźne skupiska.

**Udział klastra wśród pierwszych kupujących -> wynik tokena (AUC; kierunek z eksploracji):**

| klaster | cel | AUC eksploracja | AUC TEST | trzyma się? |
|---|---|---|---|---|
| K0 | rug | 0.554 | 0.456 | — |
| K0 | pump | 0.578 | 0.606 | TAK |
| K1 | rug | 0.507 | 0.569 | — |
| K1 | pump | 0.550 | 0.484 | — |
| K2 | rug | 0.501 | 0.479 | — |
| K2 | pump | 0.502 | 0.472 | — |
| K3 | rug | 0.556 | 0.575 | TAK |
| K3 | pump | 0.513 | 0.497 | — |

Tokenów: eksploracja 210, TEST 90.