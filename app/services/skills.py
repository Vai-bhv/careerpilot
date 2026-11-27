import re
import unicodedata

VOCAB = {
    "Power BI": ["power bi", "powerbi"],
    "SQL": ["sql", "t-sql", "postgresql", "mssql"],
    "Python": ["python"],
    "DAX": ["dax"],
    "Power Query": ["power query"],
    "Power Automate": ["power automate"],
    "Power Apps": ["power apps"],
    "Excel": ["excel"],
    "Tableau": ["tableau"],
    "ETL": ["etl"],
    "dbt": ["dbt"],
    "Airflow": ["airflow"],
    "Azure": ["azure"],
    "Fabric": ["fabric"],
    "Git": ["git"],
    "Docker": ["docker"],
    "Spark": ["spark", "pyspark"],
    "Machine learning": ["machine learning", "strojove uceni"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "REST": ["rest", "restful"],
    "Java": ["java"],
    "C++": ["c++"],
    "Kubernetes": ["kubernetes"],
    "R": ["r"],
    "AWS": ["aws"],
    "Snowflake": ["snowflake"],
    "Databricks": ["databricks"],
    "Bash": ["bash"],
    "JavaScript": ["javascript"],
    "Linux": ["linux"],
    "SAP": ["sap"],
}


def norm(value):
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", value.casefold())
            if not unicodedata.combining(c)
        ).split()
    )


def skills(text):
    value = norm(text)
    return [
        name
        for name, aliases in VOCAB.items()
        if any(re.search(r"(?<!\w)" + re.escape(x) + r"(?!\w)", value) for x in aliases)
    ]
