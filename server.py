import os

from fastapi import FastAPI, UploadFile, HTTPException
from udapi.core.document import Document

from metrics import Metric, MetricsWrapper

import rules

app = FastAPI()


@app.get("/")
def root():
    return {"this is": "dog"}


@app.post("/upload", status_code=201)
def receive_conllu(file: UploadFile):
    #read uploaded file
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


@app.post("/stats/{text_id}")
def get_stats_for_conllu(text_id: str, metric_list: list[MetricsWrapper] = None):
    #return statistics for a given id
    doc = get_doc_from_id(text_id)
    if metric_list is None:
        #return all available metrics
        return {instance.rule_id: instance.apply(doc) for instance in
                [subclass() for subclass in Metric.get_final_children()]}
    #return {'res': (metric_list[0]).metric.apply(doc)}
    return {metric.id(): metric.apply(doc) for metric in [x.metric for x in metric_list]}


@app.get("/rules/{text_id}")
def get_conllu_after_rules_applied(text_id: str):
    #return modified conllu after application of rules
    doc = get_doc_from_id(text_id)
    rules.double_adpos_rule().run(doc)
    return {"id": text_id, "document": doc.to_conllu_string()}


def get_doc_from_id(doc_id: str):
    try:
        doc = Document(filename=doc_id + ".conllu")
        return doc
    except ValueError:
        raise HTTPException(status_code=404)
