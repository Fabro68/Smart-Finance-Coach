# Smart Finance Coach
## Semana 18 — Reporte del Modelo de Riesgo Crediticio

### 1. Objetivo

Entrenar y evaluar un modelo que estime la probabilidad de incumplimiento de un préstamo, P(impago) ∈ [0, 1], a partir del dataset Gold `loan_ml_dataset` (Semana 17).

Se construyen dos modelos:

| Modelo | Uso |
|---|---|
| **Completo** (`loan_risk_full`) | Modelo general de riesgo crediticio, evaluado con todas las variables disponibles. |
| **Reducido** (`loan_risk_reduced`) | Modelo con las variables que pueden obtenerse de los usuarios del proyecto más los parámetros de un escenario de crédito. Se usará en el simulador (Semana 19). |

---

### 2. Alcance y advertencias

- El dataset de préstamos es público y sintético, y **no tiene relación verificable** con los usuarios del proyecto.
- La probabilidad calculada para un usuario es un **escenario ilustrativo**, no su riesgo crediticio real (ver `docs/ml_feature_dictionary.md`, sección 11).
- La P(impago) se mantiene separada de `financial_risk_level`, que es un indicador descriptivo basado en reglas.
- El proyecto es académico y **no constituye asesoría financiera**.
- **Predicción financiera.** La planeación del proyecto incluye "predicción financiera" en esta semana. Se considera cubierta por la estimación de P(impago), que es una predicción financiera. Las proyecciones de flujo de efectivo y capacidad de ahorro se abordarán en el simulador Monte Carlo de la Semana 19. No se construyó un pronóstico de gasto por usuario porque, con solo 3 usuarios y 21 meses de historial cada uno, no tendría validez estadística.

---

### 3. Metodología

#### 3.1. Datos y particiones

Fuente: Gold `loan_ml_dataset` (255,347 préstamos, tasa de incumplimiento 11.61%), leído en el entorno local con `deltalake`.

| Split | Filas | Uso |
|---|---|---|
| `train` | 178,743 | Ajuste de modelos y preprocesamiento. |
| `validation` | 38,302 | Comparación de modelos, selección y elección del umbral. |
| `test` | 38,302 | Evaluación final, usada **una sola vez** y solo para los modelos elegidos. |

El split es determinista y estratificado por `default` (ver `docs/ml_feature_dictionary.md`, sección 7).

#### 3.2. Configuraciones de variables

| Configuración | Variables | Propósito |
|---|---|---|
| `full` | 19 (15 numéricas, 4 categóricas) | Todas las variables candidatas. |
| `full_no_rate` | 16 | Prueba de fuga: sin `interest_rate`, `estimated_monthly_payment` ni `payment_to_income_ratio`. |
| `reduced` | 11 (`age`, `income`, `has_dependents`, `loan_amount`, `loan_term`, `interest_rate`, `loan_to_income_ratio`, `estimated_monthly_payment`, `payment_to_income_ratio`, `marital_status`, `loan_purpose`) | Variables obtenibles del usuario más parámetros del escenario. |

En el modelo reducido, `interest_rate` es un parámetro que el usuario elige en el simulador, no una decisión del banco.

#### 3.3. Preprocesamiento

- One-Hot Encoding para variables categóricas (`handle_unknown="ignore"`), ajustado **solo con `train`**.
- Escalado estándar de variables numéricas solo para la regresión logística; los modelos de árboles las reciben sin escalar.
- Preprocesamiento y modelo se guardan juntos en un `Pipeline`, de modo que el artefacto recibe las columnas originales.

#### 3.4. Modelos comparados

| Modelo | Configuración |
|---|---|
| Regresión logística | `LogisticRegression(max_iter=2000)` |
| XGBoost | Profundidad 4, tasa de aprendizaje 0.05, submuestreo 0.8, hasta 2,000 árboles con parada temprana (100 rondas sin mejora de PR-AUC en `validation`) |
| LightGBM | 31 hojas, tasa de aprendizaje 0.05, submuestreo 0.8, hasta 2,000 árboles con parada temprana (100 rondas) |

Semilla fija: 42.

#### 3.5. Desbalance de clases

Se entrenó **sin pesos de clase**. Así, las probabilidades quedan calibradas a la tasa real de incumplimiento y la P(impago) puede interpretarse como probabilidad. El desbalance se maneja con el **umbral de decisión**, elegido en `validation` como el que maximiza el F1.

Usar pesos de clase podría mejorar ligeramente el recall, pero inflaría las probabilidades y obligaría a recalibrarlas.

#### 3.6. Métricas

- **Ordenamiento:** ROC-AUC y PR-AUC. Como referencia, un modelo aleatorio tiene un PR-AUC igual a la tasa de incumplimiento (0.116).
- **Calibración:** Brier score, log loss y tabla de calibración por deciles.
- **Decisión:** precisión, recall y F1 con el umbral elegido.

No se usa accuracy: un modelo que siempre predice "no incumple" obtendría 88.4%.

---

### 4. Comparación de modelos en validation

Ordenado por PR-AUC (PR-AUC aleatorio = 0.1161):

| Configuración | Modelo | Árboles | ROC-AUC | PR-AUC | Brier | Log loss | Umbral | F1 | Precisión | Recall |
|---|---|---|---|---|---|---|---|---|---|---|
| full | **logística** | — | **0.7558** | **0.3159** | **0.0915** | **0.3128** | 0.178 | 0.3671 | 0.2908 | 0.4978 |
| full | XGBoost | 245 | 0.7543 | 0.3142 | 0.0916 | 0.3134 | 0.177 | 0.3659 | 0.2913 | 0.4919 |
| full | LightGBM | 141 | 0.7539 | 0.3129 | 0.0917 | 0.3137 | 0.173 | 0.3681 | 0.2910 | 0.5009 |
| reduced | **logística** | — | 0.7322 | 0.2868 | 0.0937 | 0.3215 | 0.176 | 0.3426 | 0.2749 | 0.4544 |
| full_no_rate | logística | — | 0.7308 | 0.2860 | 0.0938 | 0.3217 | 0.149 | 0.3357 | 0.2439 | 0.5382 |
| reduced | XGBoost | 115 | 0.7316 | 0.2857 | 0.0937 | 0.3216 | 0.179 | 0.3419 | 0.2785 | 0.4427 |
| reduced | LightGBM | 78 | 0.7311 | 0.2845 | 0.0938 | 0.3220 | 0.153 | 0.3424 | 0.2548 | 0.5216 |
| full_no_rate | XGBoost | 276 | 0.7289 | 0.2842 | 0.0939 | 0.3225 | 0.187 | 0.3345 | 0.2829 | 0.4092 |
| full_no_rate | LightGBM | 130 | 0.7289 | 0.2832 | 0.0940 | 0.3226 | 0.162 | 0.3366 | 0.2591 | 0.4804 |

#### 4.1. Elección del algoritmo: regresión logística

La propuesta del proyecto sugiere modelos basados en árboles (XGBoost o LightGBM). Ambos se entrenaron y evaluaron con las mismas reglas, pero **no superaron a la regresión logística**: en las tres configuraciones, las diferencias son de 0.001 a 0.003 en PR-AUC, con la logística ligeramente arriba.

Este resultado es coherente con un dataset sintético de relaciones casi lineales y aditivas, donde los árboles no encuentran interacciones adicionales que aprovechar. Ante un desempeño equivalente, se eligió la regresión logística por:

- ser la mejor por un margen mínimo en las tres configuraciones;
- ser interpretable mediante sus coeficientes (sección 6);
- producir probabilidades bien calibradas sin ajustes adicionales.

XGBoost y LightGBM quedan documentados como alternativas evaluadas.

#### 4.2. Análisis de sensibilidad de `interest_rate`

| Configuración (logística) | PR-AUC | ROC-AUC |
|---|---|---|
| Con `interest_rate` y derivadas (`full`) | 0.3159 | 0.7558 |
| Sin `interest_rate` ni derivadas (`full_no_rate`) | 0.2860 | 0.7308 |
| Diferencia | −0.0299 | −0.0250 |

`interest_rate` aporta información, pero su efecto es moderado: una fuga fuerte suele producir mejoras muy grandes y poco realistas. **Decisión:** se conserva en el modelo completo y se documenta este análisis. Persiste el riesgo de que la tasa refleje en parte la evaluación de riesgo del propio banco (ver `docs/ml_feature_dictionary.md`, sección 6).

#### 4.3. Costo del modelo reducido

Frente al modelo completo, el reducido pierde 0.029 de PR-AUC (0.2868 vs 0.3159) usando 11 variables en lugar de 19. Su desempeño es equivalente al de `full_no_rate`.

---

### 5. Resultados en test

Evaluación única en `test` con el umbral fijado en `validation`.

#### 5.1. Métricas

**Modelo completo** (umbral 0.178):

| Métrica | Validation | Test | Diferencia |
|---|---|---|---|
| ROC-AUC | 0.7558 | 0.7565 | +0.0007 |
| PR-AUC | 0.3159 | 0.3377 | +0.0218 |
| Brier | 0.0915 | 0.0903 | −0.0012 |
| Log loss | 0.3128 | 0.3108 | −0.0021 |

Con el umbral: precisión 0.2980, recall 0.5040, F1 0.3745.

**Modelo reducido** (umbral 0.176):

| Métrica | Validation | Test | Diferencia |
|---|---|---|---|
| ROC-AUC | 0.7322 | 0.7322 | −0.0000 |
| PR-AUC | 0.2868 | 0.3007 | +0.0139 |
| Brier | 0.0937 | 0.0930 | −0.0006 |
| Log loss | 0.3215 | 0.3203 | −0.0011 |

Con el umbral: precisión 0.2778, recall 0.4528, F1 0.3443.

**No hay sobreajuste:** las métricas de test son iguales o ligeramente mejores que las de validation. La diferencia en PR-AUC está dentro de la variación esperable entre particiones de 38,302 filas.

#### 5.2. Matriz de confusión (modelo completo, test)

| | Predicho: no incumple | Predicho: incumple |
|---|---|---|
| **Real: no incumple** | 28,572 | 5,282 |
| **Real: incumple** | 2,206 | 2,242 |

El modelo detecta 2,242 de 4,448 incumplimientos (50.4%). De cada 10 préstamos marcados como riesgosos, aproximadamente 3 incumplen, frente a 1.2 si se marcaran al azar.

#### 5.3. Calibración

Probabilidad media predicha frente a tasa real, por decil de riesgo (1 = menor riesgo):

| Decil | Completo: predicho | Completo: observado | Reducido: predicho | Reducido: observado |
|---|---|---|---|---|
| 1 | 0.0172 | 0.0222 | 0.0233 | 0.0271 |
| 2 | 0.0305 | 0.0347 | 0.0374 | 0.0402 |
| 3 | 0.0430 | 0.0426 | 0.0503 | 0.0509 |
| 4 | 0.0566 | 0.0548 | 0.0638 | 0.0595 |
| 5 | 0.0724 | 0.0692 | 0.0788 | 0.0731 |
| 6 | 0.0922 | 0.0916 | 0.0972 | 0.0966 |
| 7 | 0.1174 | 0.1097 | 0.1209 | 0.1183 |
| 8 | 0.1529 | 0.1460 | 0.1518 | 0.1525 |
| 9 | 0.2089 | 0.2107 | 0.2001 | 0.2034 |
| 10 | 0.3747 | 0.3798 | 0.3420 | 0.3396 |

- Las probabilidades predichas coinciden con las tasas observadas en todos los deciles: **la P(impago) es interpretable como probabilidad**.
- La probabilidad media predicha (0.1166) coincide con la tasa real de test (0.1161).
- El decil de mayor riesgo incumple 38% de las veces, frente a 2% del de menor riesgo (unas 17 veces más).

---

### 6. Interpretación del modelo completo

Coeficientes de la regresión logística. Las variables numéricas están estandarizadas, por lo que sus coeficientes son comparables entre sí: indican el cambio en el logaritmo de las probabilidades (log-odds) por cada desviación estándar. Un coeficiente positivo aumenta el riesgo.

**Variables numéricas principales:**

| Variable | Coeficiente | Lectura |
|---|---|---|
| `age` | −0.60 | Mayor edad, menor riesgo. |
| `loan_to_income_ratio` | +0.48 | Préstamo mayor respecto al ingreso, mayor riesgo. |
| `interest_rate` | +0.47 | Mayor tasa, mayor riesgo. |
| `months_employed` | −0.35 | Mayor antigüedad laboral, menor riesgo. |
| `credit_score` | −0.12 | Mayor puntaje, menor riesgo. |
| `num_credit_lines` | +0.11 | Más líneas de crédito, mayor riesgo. |

**Variables categóricas.** El One-Hot conserva todas las categorías, por lo que los coeficientes se interpretan **comparando categorías de la misma variable**, no por su signo:

| Variable | Menor riesgo | Mayor riesgo | Diferencia |
|---|---|---|---|
| `employment_type` | Full-time (−0.54) | Unemployed (−0.08) | 0.47 |
| `marital_status` | Married (−0.53) | Divorced (−0.30) | 0.23 |
| `education` | PhD (−0.42) | High School (−0.16) | 0.26 |
| `loan_purpose` | Home (−0.40) | Business (−0.15) | 0.24 |

**Precaución con variables correlacionadas.** `income` (+0.016), `loan_amount` (−0.023), `estimated_monthly_payment` (+0.030) y `payment_to_income_ratio` (−0.014) tienen coeficientes cercanos a cero porque su efecto lo captura `loan_to_income_ratio`, con la que están fuertemente relacionadas. Sus coeficientes individuales no deben interpretarse por separado.

Estas relaciones describen asociaciones en un dataset sintético; no deben interpretarse como relaciones causales.

---

### 7. Artefactos y reproducción

#### 7.1. Scripts

| Script | Función |
|---|---|
| `src/ml/loan_features.py` | Carga del dataset, configuraciones de variables y preprocesamiento. |
| `src/ml/train_loan_model.py` | Entrena y compara los 9 modelos en `validation`. |
| `src/ml/evaluate_loan_model.py` | Evalúa los modelos elegidos en `test` y genera los artefactos finales. |

Ejecución en el entorno local (`requirements.txt`, Python 3.13):

```powershell
python src/ml/train_loan_model.py
python src/ml/evaluate_loan_model.py
```

El entrenamiento se ejecuta en el entorno local y no en el contenedor de Spark, que usa Python 3.8 y no incluye librerías de Machine Learning.

#### 7.2. Artefactos generados (carpeta `models/`, fuera de git)

| Archivo | Contenido |
|---|---|
| `models/loan_risk_full.joblib` | Pipeline final del modelo completo. |
| `models/loan_risk_reduced.joblib` | Pipeline final del modelo reducido. |
| `models/model_card.json` | Variables, umbral, métricas, rango de ingreso de entrenamiento y advertencias de uso. |
| `models/validation_results.json` | Métricas de los 9 modelos en `validation`. |
| `models/test_results.json` | Métricas en `test`, calibración y coeficientes. |
| `models/candidates/` | Los 9 pipelines candidatos. |

Los artefactos se regeneran con los scripts y no se versionan, de acuerdo con la regla del proyecto de no agregar resultados generados al repositorio.

Los modelos finales **no se reentrenan** con `train` + `validation`: el artefacto guardado es exactamente el modelo evaluado.

---

### 8. Limitaciones

1. **Desempeño modesto.** Un ROC-AUC de 0.756 y un PR-AUC de 0.338 superan claramente al azar, pero el modelo está lejos de separar con precisión a quienes incumplen. Es coherente con las correlaciones débiles del dataset (máxima +0.179).
2. **Dataset sintético.** Las distribuciones casi uniformes y los montos altos respecto al ingreso indican datos simulados; los resultados no deben extrapolarse a carteras reales.
3. **Posible fuga en `interest_rate`.** Ver sección 4.2.
4. **Sin relación con los usuarios del proyecto.** El modelo se entrenó con préstamos que no corresponden a los usuarios del dashboard.
5. **Ingresos fuera del rango de entrenamiento.** La regresión logística extrapola linealmente fuera del rango de `income` visto en entrenamiento (15,000–149,999). Dos de los tres usuarios con transacciones quedan por debajo de ese rango, por lo que sus estimaciones son poco confiables.
6. **Interpretación asociativa.** Los coeficientes describen asociaciones, no causas.
