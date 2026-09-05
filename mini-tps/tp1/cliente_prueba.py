"""
Pruebas de caso de uso de la API de predicción de ACV.
Dispara un caso válido y uno inválido, para verificar que el contrato.
"""
import requests

URL = "http://localhost:8080"

CASO_VALIDO = {
    "gender": "Male",
    "age": 67.0,
    "hypertension": 0,
    "heart_disease": 1,
    "ever_married": "Yes",
    "work_type": "Private",
    "Residence_type": "Urban",
    "avg_glucose_level": 228.69,
    "bmi": 36.6,
    "smoking_status": "formerly smoked",
}

# Paciente con varios campos fuera del contrato:
#   age                -> supera el máximo permitido (100)
#   work_type          -> no está entre los valores aceptados
#   avg_glucose_level  -> negativo, viola gt=0
CASO_INVALIDO = {
    "gender": "Female",
    "age": 200,
    "hypertension": 0,
    "heart_disease": 0,
    "ever_married": "Yes",
    "work_type": "astronauta",
    "Residence_type": "Rural",
    "avg_glucose_level": -5.0,
    "bmi": 27.4,
    "smoking_status": "never smoked",
}


print("--- Health check ---")
resp_health = requests.get(f"{URL}/health")
print(f"Status: {resp_health.status_code} | Respuesta: {resp_health.json()}\n")

print("--- Caso VÁLIDO (esperado 200) ---")
resp_valido = requests.post(f"{URL}/v1/predict", json=CASO_VALIDO)
print(f"Status: {resp_valido.status_code} | Respuesta: {resp_valido.json()}\n")

print("--- Caso INVÁLIDO (esperado 422) ---")
resp_invalido = requests.post(f"{URL}/v1/predict", json=CASO_INVALIDO)
print(f"Status: {resp_invalido.status_code} | Respuesta: {resp_invalido.json()}")
