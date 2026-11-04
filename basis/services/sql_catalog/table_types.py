# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Table type vocabulary used by the vendored SQL catalog engines."""

from __future__ import annotations


class TableTypes:
    """Canonical ``table_type`` values, in Postgres ``information_schema`` style."""

    VIEW = "view"
    MATERIALIZED_VIEW = "materialized view"
    BASE_TABLE = "base table"

    LIST_OF_ALL = [
        VIEW,
        MATERIALIZED_VIEW,
        BASE_TABLE,
    ]
