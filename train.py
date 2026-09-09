# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import kagglehub
import os

path = kagglehub.dataset_download("laotse/credit-risk-dataset")

csv_filename = [f for f in os.listdir(path) if f.endswith('.csv')][0]
csv_path = os.path.join(path, csv_filename)
# csv_path = "data/credit_risk_dataset.csv"

df = pd.read_csv(csv_path)
print(df.shape)
df.head()
from optbinning import BinningProcess, OptimalBinning

sns.set_theme(style="whitegrid")
pd.set_option('display.max_columns', None)

# %%
# nulos
print(df.isnull().sum()[df.isnull().sum() > 0])

# como viene el target. 1 = moroso
default_dist = df['loan_status'].value_counts(normalize=True) * 100
print(default_dist.round(2).astype(str) + '%')

# %%
target_col = 'loan_status'

X = df.drop(columns=[target_col])
y = df[target_col]

# optbinning necesita que le pase cuales son categoricas
categorical_cols = X.select_dtypes(include=['object', 'category']).columns.tolist()
numerical_cols = X.select_dtypes(include=['int64', 'float64']).columns.tolist()

print(len(categorical_cols), categorical_cols)
print(len(numerical_cols), numerical_cols)

# %%
from sklearn.model_selection import train_test_split

X_train_raw, X_test_raw, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)

# %%
from optbinning import BinningProcess

# esto lo tenia con X entero y estaba mal: los cortes del binning veian el
# target del test y el gini me daba mas alto de lo que era. va solo con train
binning_process = BinningProcess(
    variable_names=list(X.columns),
    categorical_variables=categorical_cols
)

binning_process.fit(X_train_raw, y_train)

iv_summary = (
    binning_process.summary()
    .sort_values(by="iv", ascending=False)
)

iv_summary

# %%
# el scorecard despues quiere raw, la logistica quiere woe
X_train_woe = binning_process.transform(X_train_raw, metric="woe")
X_test_woe = binning_process.transform(X_test_raw, metric="woe")

# %%

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

model = LogisticRegression(random_state=42)
# si tira el warning de convergencia, subir max_iter
model.fit(X_train_woe, y_train)

y_pred_proba_test = model.predict_proba(X_test_woe)[:, 1]

auc_test = roc_auc_score(y_test, y_pred_proba_test)
gini_test = 2 * auc_test - 1
print(f"Gini Test: {gini_test:.4f}")

# %%
# esta es la de mayor IV, miro como quedaron los cortes
optb = binning_process.get_binned_variable("loan_percent_income")
optb.binning_table.build()

# %%
from scipy.stats import ks_2samp

good_probs = y_pred_proba_test[y_test == 0]
bad_probs = y_pred_proba_test[y_test == 1]

ks_stat, p_value = ks_2samp(good_probs, bad_probs)

print(f"Estadístico KS (Test): {ks_stat * 100:.2f}%")

# %%
from optbinning import Scorecard

scorecard = Scorecard(
    binning_process=binning_process,
    estimator=model,
    scaling_method="min_max",
    scaling_method_params={"min": 300, "max": 850}
)

# tener en cuenta: raw, no woe. la primera vez le pase el woe y salia cualquier cosa
scorecard.fit(X_train_raw, y_train)

scorecard_table = scorecard.table(style="summary")
scorecard_table

# %%
df_resultado = df.copy()
df_resultado['Score'] = scorecard.score(X).round().astype(int)

df_resultado[['person_age', 'person_income', 'loan_intent', 'loan_amnt', 'Score', 'loan_status']].head(10)

# %%
import seaborn as sns
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 5))
sns.histplot(data=df_resultado, x='Score', hue='loan_status', bins=30, kde=True, palette={0: 'green', 1: 'red'})
plt.title('Distribución del Score de Crédito por Estado de Préstamo')
plt.xlabel('Credit Score (300 - 850)')
plt.ylabel('Cantidad de Clientes')
plt.show()

# %%
import pandas as pd

# tener en cuenta: esto corre sobre df entero, o sea 70% son datos que el modelo ya vio.
# para elegir el corte en serio habria que hacerlo solo con test
thresholds = range(450, 775, 25)
estrategia = []

total_clientes = len(df_resultado)
total_defaults = df_resultado['loan_status'].sum()

for cut in thresholds:
    aprobados = df_resultado[df_resultado['Score'] >= cut]
    rechazados = df_resultado[df_resultado['Score'] < cut]
    
    num_aprobados = len(aprobados)
    pct_aprobados = (num_aprobados / total_clientes) * 100
    
    num_defaults_aprobados = aprobados['loan_status'].sum()
    bad_rate_aprobados = (num_defaults_aprobados / num_aprobados * 100) if num_aprobados > 0 else 0
    
    # morosos que me ahorro rechazando
    defaults_rechazados = rechazados['loan_status'].sum()
    bad_capture = (defaults_rechazados / total_defaults * 100)
    
    estrategia.append({
        'corte': cut,
        '% aprobados': round(pct_aprobados, 1),
        'cant_aprobados': num_aprobados,
        'bad_rate': round(bad_rate_aprobados, 2),
        'bad_capture': round(bad_capture, 1)
    })

df_estrategia = pd.DataFrame(estrategia)
df_estrategia

# %%
bins_score = [0, 500, 570, 640, 720, 900]
labels_riesgo = ['E (Muy Alto)', 'D (Alto)', 'C (Medio)', 'B (Bajo)', 'A (Muy Bajo)']

df_resultado['Banda_Riesgo'] = pd.cut(df_resultado['Score'], bins=bins_score, labels=labels_riesgo)

resumen_bandas = df_resultado.groupby('Banda_Riesgo', observed=False).agg(
    Cant_Clientes=('loan_status', 'count'),
    Cant_Defaults=('loan_status', 'sum'),
    Tasa_Default=('loan_status', 'mean')
).reset_index()

resumen_bandas['% del Total'] = (resumen_bandas['Cant_Clientes'] / len(df_resultado) * 100).round(1)
resumen_bandas['Tasa_Default (% Mora)'] = (resumen_bandas['Tasa_Default'] * 100).round(2)

resumen_bandas

# %%
import matplotlib.pyplot as plt

fig, ax1 = plt.subplots(figsize=(10, 5))

ax1.set_xlabel('Punto de Corte (Score)')
ax1.set_ylabel('% Aprobación', color='tab:blue')
ax1.plot(df_estrategia['corte'], df_estrategia['% aprobados'], color='tab:blue', marker='o', linewidth=2, label='% Aprobación')
ax1.tick_params(axis='y', labelcolor='tab:blue')
ax1.grid(True, alpha=0.3)

ax2 = ax1.twinx()  
ax2.set_ylabel('Tasa Mora Aprobados (% Bad Rate)', color='tab:red')
ax2.plot(df_estrategia['corte'], df_estrategia['bad_rate'], color='tab:red', marker='s', linestyle='--', linewidth=2, label='% Mora')
ax2.tick_params(axis='y', labelcolor='tab:red')

plt.title('Estrategia de Admisión: Tasa de Aprobación vs Tasa de Morosidad')
fig.tight_layout()
plt.show()

# %%
def evaluar_solicitante(datos_cliente, scorecard, cutoff_aprobacion=600, cutoff_revision=530):
    df_cliente = pd.DataFrame([datos_cliente])
    score = int(round(scorecard.score(df_cliente)[0]))
    
    if score >= cutoff_aprobacion:
        decision = "APROBADO"
        recomendacion = "Otorgar préstamo con tasa estándar / preferencial."
    elif score >= cutoff_revision:
        decision = "REVISIÓN MANUAL"
        recomendacion = "Solicitar documentación adicional (recibo de sueldo, garantes)."
    else:
        decision = "RECHAZADO"
        recomendacion = "Rechazar solicitud. Nivel de riesgo superior al tolerado."
    
    print(f"score {score} -> {decision}")
    print(recomendacion)
    
    return {'score': score, 'decision': decision}


# testeamoooo
nuevo_solicitante = {
    'person_age': 28,
    'person_income': 65000,
    'person_home_ownership': 'RENT',
    'person_emp_length': 4.0,
    'loan_intent': 'PERSONAL',
    'loan_grade': 'B',
    'loan_amnt': 8000,
    'loan_int_rate': 11.2,
    'loan_percent_income': 0.12,
    'cb_person_default_on_file': 'N',
    'cb_person_cred_hist_length': 5
}

resultado = evaluar_solicitante(nuevo_solicitante, scorecard, cutoff_aprobacion=600, cutoff_revision=530)

# %%
scorecard_export = scorecard.table(style="summary")
scorecard_export['Points'] = scorecard_export['Points'].round(2)
scorecard_export.to_csv("outputs/Scorecard_Credito_Puntos.csv", index=False)

scorecard_export.head(15)

# %%
import pickle

modelo_completo = {
    'binning_process': binning_process,
    'scorecard': scorecard,
    'cutoff_aprobacion': 600,
    'cutoff_revision': 570,
    'gini': gini_test,
    'ks': ks_stat * 100
}

with open("models/scorecard_model.pkl", "wb") as f:
    pickle.dump(modelo_completo, f)

print("guardado. gini", round(gini_test, 4), "ks", round(ks_stat * 100, 2))

# %%



