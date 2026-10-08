"""Traduccion entre los enum del .proto y los textos con los que se entreno el modelo.
"""
import scoring_pb2

MAPAS = {
    "gender": {
        scoring_pb2.GENERO_MALE: "Male",
        scoring_pb2.GENERO_FEMALE: "Female",
        scoring_pb2.GENERO_OTHER: "Other",
    },
    "ever_married": {
        scoring_pb2.ESTADO_CIVIL_YES: "Yes",
        scoring_pb2.ESTADO_CIVIL_NO: "No",
    },
    "work_type": {
        scoring_pb2.TIPO_TRABAJO_PRIVATE: "Private",
        scoring_pb2.TIPO_TRABAJO_SELF_EMPLOYED: "Self-employed",
        scoring_pb2.TIPO_TRABAJO_GOVT_JOB: "Govt_job",
        scoring_pb2.TIPO_TRABAJO_CHILDREN: "children",
        scoring_pb2.TIPO_TRABAJO_NEVER_WORKED: "Never_worked",
    },
    "Residence_type": {
        scoring_pb2.TIPO_RESIDENCIA_URBAN: "Urban",
        scoring_pb2.TIPO_RESIDENCIA_RURAL: "Rural",
    },
    "smoking_status": {
        scoring_pb2.TABAQUISMO_FORMERLY_SMOKED: "formerly smoked",
        scoring_pb2.TABAQUISMO_NEVER_SMOKED: "never smoked",
        scoring_pb2.TABAQUISMO_SMOKES: "smokes",
        scoring_pb2.TABAQUISMO_UNKNOWN: "Unknown",
    },
}

INVERSOS = {
    campo: {texto: enum for enum, texto in mapa.items()}
    for campo, mapa in MAPAS.items()
}
