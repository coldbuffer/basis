# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Errors raised when a catalog driver cannot describe every relation it listed."""

from __future__ import annotations


class IncompleteCatalogExtractionError(RuntimeError):
    """A listed relation could not be described, so the snapshot would be partial."""
