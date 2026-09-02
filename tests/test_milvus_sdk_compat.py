from data_pipeline.milvus_loader import EMBEDDING_DIM, MilvusRuleLoader


def test_milvus_collection_uses_1024_dim(tmp_path):
    loader = MilvusRuleLoader(uri=tmp_path / "compat.db", embedding_client=object())
    loader.create_collection()
    fields = {field["name"]: field for field in loader.client.describe_collection(loader.collection_name)["fields"]}
    assert fields["embedding"]["params"]["dim"] == EMBEDDING_DIM
