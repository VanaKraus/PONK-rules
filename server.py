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
    # filtered_nodes = list(node for node in doc.nodes if node.upos != "PUNCT")
    # sentences = len(list(doc.bundles))
    # words = len(filtered_nodes)
    # chars = sum(len(node.form) for node in filtered_nodes)
    # return {
    #   "id": text_id,
    #   "sents": sentences,
    #   "words": words,
    #   "chars": chars,
    #   "CLI": 0.047 * (chars/words) * 100 - 0.286 * (sentences/words) * 100 - 12.9,
    #   "ARI": 3.666 * (chars/words) + 0.631 * (words/sentences) - 19.491, #formula in Cinkova 2021 has parens switched
    #   "num_hapax": metrics.Metric.build_from_string("num_hapax:use_lemma=True").apply(doc),
    #   "entropy": metrics.Entropy(use_lemma=True).apply(doc)
    # }
    if metric_list is None:
        #return all available metrics
        return {"hi": "hello"}
    return {'res': (metric_list[0]).metric.apply(doc)}


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
