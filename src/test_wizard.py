#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for tkinter wizard
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Import config first
from config import DB_NAME, CAUSALI_JSON, CONFIG_JSON, SEC_DOCS, DEFAULT_CONFIG, SEC_CATEGORIES, DOCS_BASE

# Set paths before any module use
from database import set_db_path
from causali import set_causali_path
from config_manager import set_config_paths
from utils import set_docs_base

set_db_path(DB_NAME)
set_causali_path(CAUSALI_JSON)
set_config_paths(CONFIG_JSON, SEC_DOCS, DEFAULT_CONFIG, list(SEC_CATEGORIES))
set_docs_base(DOCS_BASE)

from tkinter_wizard import WizardController, WizardState

def test_wizard_save():
    """Test wizard configuration saving"""
    print("Testing wizard configuration saving...")

    # Create wizard state with test data
    state = WizardState()
    state.section_data = {
        'nome_sezione': 'Test Section',
        'codice_sezione': 'TS001',
        'sede_operativa': 'Test Address',
        'sede_legale': 'Test Legal Address',
        'indirizzo_postale': 'Test Postal Address',
        'email': 'test@example.com',
        'telefono': '123456789',
        'sito_web': 'http://test.com',
        'coordinate_bancarie': 'Test Bank Details',
        'recapiti': 'Test Contacts',
        'mandato': 'Test Mandate',
    }
    state.completed = True

    # Create wizard controller
    controller = WizardController(state, mode="FIRST_RUN")

    # Simulate save
    controller._on_save()

    print("Wizard save completed. Checking if config file was created...")

    # Check if config file exists
    if os.path.exists(CONFIG_JSON):
        print(f"✓ Config file created at: {CONFIG_JSON}")
        with open(CONFIG_JSON, 'r', encoding='utf-8') as f:
            saved_config = f.read()
        print("Saved config content:")
        print(saved_config)
        return True
    else:
        print(f"✗ Config file NOT created at: {CONFIG_JSON}")
        return False

if __name__ == "__main__":
    success = test_wizard_save()
    sys.exit(0 if success else 1)