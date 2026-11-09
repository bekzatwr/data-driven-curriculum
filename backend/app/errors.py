import csv
import io

from fastapi.responses import JSONResponse, Response


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []

    def response(self, as_csv=False):
        if as_csv and self.details:
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(["file", "row", "field", "reason"])
            for detail in self.details:
                cells = [str(detail.get(key) or "") for key in ("file", "row", "field", "reason")]
                # CSV quoting alone does not neutralize spreadsheet formulas.
                writer.writerow(["'" + c if c.startswith(("=", "+", "-", "@")) else c for c in cells])
            return Response(
                stream.getvalue().encode("utf-8-sig"), status_code=self.status,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="import-errors.csv"'},
            )
        return JSONResponse(status_code=self.status, content={
            "code": self.code, "message": self.message,
            "details": self.details[:100], "total_errors": len(self.details),
        })
