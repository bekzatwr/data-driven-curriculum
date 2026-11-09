"""Versioned, revalidated data exchange without restoring database IDs or trust labels."""
import csv
import hashlib
import hmac
import io

from .config import Settings
from .db import Store
from .errors import ApiError
from .schemas import DatasetPackage, PackageData
from .validation import RESULT_FIELDS, TOPIC_FIELDS, canonical, validate_upload


def package_checksum(data: PackageData) -> str:
    # The checksum covers the typed JSON data in its existing array order.
    return hashlib.sha256(canonical(data.model_dump(mode="json")).encode("utf-8")).hexdigest()


def export_package(store: Store, dataset_id: str) -> DatasetPackage:
    dataset = store.get_dataset(dataset_id)
    data = PackageData(metadata=dataset["metadata"], curriculum=store.get_topics(dataset_id),
                       results=store.load_results(dataset_id))
    return DatasetPackage(format="ddc-dataset", version=1, data=data, checksum=package_checksum(data))


def _csv(fields, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def validate_package(package: DatasetPackage, settings: Settings):
    if not hmac.compare_digest(package.checksum, package_checksum(package.data)):
        raise ApiError(422, "PACKAGE_CHECKSUM_MISMATCH", "Контрольная сумма пакета не совпадает с данными.")
    data = package.data.model_dump(mode="json")
    topics = [{**topic, "is_locked": str(topic["is_locked"]).lower()} for topic in data["curriculum"]]
    # Run the same cross-field, date, pair and row-limit checks as CSV import.
    # JSON has its own bounded body; normalized CSV bytes need not match the original file size.
    # source_type is always upload, including when the original package came from demo.
    return validate_upload(_csv(RESULT_FIELDS, data["results"]), _csv(TOPIC_FIELDS, topics),
                           canonical(data["metadata"]), settings, source_type="upload", enforce_csv_size=False)
