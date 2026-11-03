"""RQ worker entrypoint: `python -m tracelume.worker`."""

from redis import Redis
from rq import Worker

from tracelume.config import get_settings
from tracelume.db import init_db


def main() -> None:
    init_db()
    conn = Redis.from_url(get_settings().redis_url)
    Worker(["tracelume"], connection=conn).work()


if __name__ == "__main__":
    main()
