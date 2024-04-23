import os

from fastapi import FastAPI, UploadFile, HTTPException
from udapi.core.document import Document

from metrics import Metric, MetricsWrapper

from rules import Rule, RuleBlockWrapper, RuleAPIWrapper

from pydantic import BaseModel

app = FastAPI(
    title='PONK Rules',
    swagger_ui_parameters={"defaultModelsExpandDepth": 0}
)


@app.get("/")
def root():
    return {"this is": "dog"}


@app.post("/upload", status_code=201)
def receive_conllu(file: UploadFile):
    # read uploaded file
    file_id = os.urandom(8).hex()
    filename = file_id + ".conllu"
    with open(filename, "wb") as local_copy:
        local_copy.write(file.file.read())
    try:
        Document(filename=filename)
        return {"file_id": file_id}
    except ValueError as e:
        local_copy.close()
        os.remove(filename)
        raise HTTPException(status_code=406, detail=f"{type(e).__name__}: {str(e)}")


class MetricsReply(BaseModel):
    results: list[dict[str, int | float]]
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {"word_count": 42},
                        {"ari": 17.6}
                    ]
                }
            ]
        }
    }


@app.post("/stats/{text_id}")
def get_stats_for_conllu(text_id: str, metric_list: list[MetricsWrapper] | None = None) -> MetricsReply:
    # return statistics for a given id
    doc = get_doc_from_id(text_id)
    if metric_list is None:
        # return all available metrics
        results = [{instance.metric_id: instance.apply(doc)} for instance in
                   [subclass() for subclass in Metric.get_final_children()]]
    else:
        results = [{metric.metric_id: metric.apply(doc)} for metric in [x.metric for x in metric_list]]
    return MetricsReply(results=results)


class RulesReply(BaseModel):
    id: str
    document: str
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "deadbeef12345678",
                    "document": "A conllu string",
                }
            ]
        }
    }


@app.post("/rules/{text_id}")
def get_conllu_after_rules_applied(text_id: str, rule_list: list[RuleAPIWrapper] | None = None) -> RulesReply:
    # return modified conllu after application of rules
    doc = get_doc_from_id(text_id)
    rules = [rule() for rule in Rule.get_final_children()] if rule_list is None else [item.rule for item in rule_list]
    for rule in rules:
        RuleBlockWrapper(rule).run(doc)
    return RulesReply(id=text_id, document=doc.to_conllu_string())


def get_doc_from_id(doc_id: str):
    try:
        doc = Document(filename=doc_id + ".conllu")
        return doc
    except ValueError:
        raise HTTPException(status_code=404)
