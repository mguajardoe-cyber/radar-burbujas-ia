| cifra | declarado | recalculado | fuente | estado | nota |
|---|---|---|---|---|---|
| Caída del Nasdaq en la puntocom | −77,9% (5.048 → 1.114) | -77.93% (5048.62 → 1114.11) | data/raw/IXIC_desde_1990.csv | OK |  |
| Variación del Nasdaq en octubre de 2026 | −5,3% | -5.30% (26861.06 → 25437.00) | data/raw/precios_diarios.csv | OK |  |
| Universo | 9 acciones + 2 índices | 11 series en data/raw (9 + ^IXIC, ^GSPC) | data/raw/precios_diarios.csv | OK |  |
| Ventana y largo mínimo | 260 y 31 | 260 y floor((0,01+1,8/√260)·260) = 31 | src/config.py | OK |  |
| Umbrales amarillo / rojo | 0,36 / 0,69 | 0.351 ± 0.023 / 0.716 ± 0.022 (5.000 sim, semilla 2026; z = -0.3 / +0.9) | audit/a2_detector.py | OK |  |
| Persistencia | 6 semanas | 6 (log(260) = 5.56) | src/config.py | OK |  |
| Duración de main.py | 14,6 s normal; ~6-11 s offline | normal máx 14.6 s; offline 5.9-10.9 s | logs/ | OK |  |
| Meta de series válidas | 98% | 0.98 | src/config.py | OK |  |
| Semáforo actual | TSM rojo 23 semanas; AMD amarillo 11 | TSM rojo 23; AMD amarillo 11 | audit/a2_detector.py | OK |  |
| Anticipación puntocom | 11 semanas (16 sin persistencia) | 11 (16 sin persistencia) | audit/a3_backtest.py | OK |  |
| Falsas burbujas en 2008 y 2022 (Nasdaq) | 0 | semanas en rojo con persistencia: 2007-2009 = 0, 2021-2022 = 0 (bruto: 7 y 0) | audit/a3_backtest.py | OK |  |
| Anticipación Nikkei 1989 | 45 semanas | 45 | audit/a3_backtest.py | OK |  |
| Anticipación Bitcoin 2021 | 42 semanas | 42 | audit/a3_backtest.py | OK |  |
| IL3 | 11/11 válidas; 100% de columnas documentadas | 11/11; 100% | a1 + docs/diccionario_datos.csv | OK |  |
| IL4 (según logs) | 6/6 sin error | 6/6 sin error | logs/ | OK | El total crece con cada ejecución; se actualiza en el cierre |
| Episodios rojos del universo | 204 → 32 | 204 → 32 | audit/a4_cifras.py | OK |  |
| % de semanas en rojo del universo | 6,6% → 4,3% | 6.6% → 4.3% | audit/a4_cifras.py | OK |  |
| Falsas alarmas por serie sin burbuja | 16,9 → 2,7 | 17.6 ± 0.4 → 2.9 ± 0.1 (200 sim, semilla 2027) | audit/a4_cifras.py | OK |  |
| Series en rojo desde 2023 | 8 de 11 (señal bruta) | bruta: 8 (NVDA, MSFT, GOOGL, META, AMD, AVGO, TSM, ORCL); con persistencia: 6 | audit/a4_cifras.py | OK | La cifra declarada usa la señal bruta; con persistencia el número es distinto |
| Caídas máx. mantener / v1 / v2 — Nasdaq 2000-2002 | -77.4% / -73.2% / -64.8% | -77.4% / -73.2% / -64.8% | audit/a3_backtest.py | OK |  |
| Caídas máx. mantener / v1 / v2 — Nasdaq 2007-2009 | -54.0% / -54.0% / -54.0% | -54.0% / -54.0% / -54.0% | audit/a3_backtest.py | OK |  |
| Caídas máx. mantener / v1 / v2 — Nasdaq 2021-2022 | -35.7% / -35.7% / -35.7% | -35.7% / -35.7% / -35.7% | audit/a3_backtest.py | OK |  |
| Caídas máx. mantener / v1 / v2 — Nasdaq periodo completo | -77.4% / -73.2% / -64.8% | -77.4% / -73.2% / -64.8% | audit/a3_backtest.py | OK |  |
| Caídas máx. mantener / v1 / v2 — Cartera B 2018-hoy (9 acciones) | -45.4% / -43.5% / -37.9% | -45.4% / -43.5% / -37.9% | audit/a3_backtest.py | OK |  |
| Caídas máx. mantener / v1 / v2 — Nikkei 1989 | -61.9% / -61.9% / -57.7% | -61.9% / -61.9% / -57.7% | audit/a3_backtest.py | OK |  |
| Caídas máx. mantener / v1 / v2 — Bitcoin 2021 | -74.2% / -74.2% / -53.5% | -74.2% / -74.2% / -53.5% | audit/a3_backtest.py | OK |  |
| Percentil placebo — Nasdaq completo v1 | 53.5 | 14.5 (generador propio, semilla 2026) | audit/a3_backtest.py | DIFERENCIA | tolerancia ±7.2 (error Monte Carlo) |
| Percentil placebo — Nasdaq completo v2 | 3.1 | 11.4 (generador propio, semilla 2026) | audit/a3_backtest.py | DIFERENCIA | tolerancia ±2.8 (error Monte Carlo) |
| Percentil placebo — Cartera B v1 | 97.5 | 47.7 (generador propio, semilla 2026) | audit/a3_backtest.py | DIFERENCIA | tolerancia ±2.6 (error Monte Carlo) |
| Percentil placebo — Cartera B v2 | 3.9 | 27.4 (generador propio, semilla 2026) | audit/a3_backtest.py | DIFERENCIA | tolerancia ±3.1 (error Monte Carlo) |
| Percentil placebo — Nikkei 1989 v2 | 52.5 | 52.2 (generador propio, semilla 2026) | audit/a3_backtest.py | OK | tolerancia ±7.2 (error Monte Carlo) |
| Percentil placebo — Bitcoin 2021 v2 | 26.0 | 13.7 (generador propio, semilla 2026) | audit/a3_backtest.py | DIFERENCIA | tolerancia ±6.4 (error Monte Carlo) |
| Retorno anual y Sharpe mantener / v1 / v2 — Nasdaq completo | 11.7% / 12.1% / 11.1% · 0.61 / 0.64 / 0.63 | 11.7% / 12.1% / 11.1% · 0.61 / 0.64 / 0.63 | audit/a3_backtest.py | OK |  |
| Retorno anual y Sharpe mantener / v1 / v2 — Cartera B | 33.7% / 33.6% / 31.5% · 1.21 / 1.27 / 1.31 | 33.7% / 33.6% / 31.5% · 1.21 / 1.27 / 1.31 | audit/a3_backtest.py | OK |  |
