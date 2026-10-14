"""Import-specific recovery contract, separate from ordinary API errors."""

from . import db


class ImportFailure(Exception):
    def __init__(self, detail, code, scope="batch", status=400, uncertain=False):
        self.detail = detail
        self.code = code
        self.scope = scope
        self.status = status
        self.uncertain = uncertain


def preparation_jobs(project_id, connection=None, asset_id=None):
    sql = """SELECT id,status,progress,message,json_extract(payload,'$.asset_id') AS asset_id
             FROM jobs WHERE project_id=? AND kind='normalize'"""
    params = [project_id]
    if asset_id is not None:
        sql += " AND json_extract(payload,'$.asset_id')=?"
        params.append(asset_id)
    sql += " ORDER BY created DESC,rowid DESC"
    rows = (
        connection.execute(sql, params).fetchall()
        if connection is not None
        else db.rows(sql, params)
    )
    latest = {}
    for row in rows:
        row = dict(row)
        aid = row.pop("asset_id")
        latest.setdefault(aid, row)
    return latest
