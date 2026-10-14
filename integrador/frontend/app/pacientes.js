export const PACIENTES = [
  {
    nombre: "Riesgo alto",
    detalle: "El caso de referencia: tiene que dar 0.5005481839179993 por los tres protocolos",
    datos: {
      gender: "Female", age: 67, hypertension: 0, heart_disease: 1,
      ever_married: "Yes", work_type: "Private", Residence_type: "Urban",
      avg_glucose_level: 228.69, bmi: 36.6, smoking_status: "formerly smoked",
    },
  },
  {
    nombre: "Riesgo bajo",
    detalle: "Joven, sin antecedentes y con glucosa normal: queda debajo del umbral",
    datos: {
      gender: "Male", age: 25, hypertension: 0, heart_disease: 0,
      ever_married: "No", work_type: "Private", Residence_type: "Urban",
      avg_glucose_level: 85.3, bmi: 22.4, smoking_status: "never smoked",
    },
  },
  {
    nombre: "Sin BMI",
    detalle: "No manda bmi: la plataforma lo imputa por grupo etario, como en el entrenamiento",
    datos: {
      gender: "Female", age: 58, hypertension: 1, heart_disease: 0,
      ever_married: "Yes", work_type: "Self-employed", Residence_type: "Rural",
      avg_glucose_level: 171.23, bmi: null, smoking_status: "smokes",
    },
  },
  {
    nombre: "Inválido",
    detalle: "Edad 150, un trabajo inventado y glucosa negativa: REST y GraphQL tienen que rechazarlo igual",
    datos: {
      gender: "Female", age: 150, hypertension: 0, heart_disease: 1,
      ever_married: "Yes", work_type: "Astronauta", Residence_type: "Urban",
      avg_glucose_level: -3, bmi: 36.6, smoking_status: "formerly smoked",
    },
  },
]
