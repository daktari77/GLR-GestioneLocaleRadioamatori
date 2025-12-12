# Test Suite Documentation

## Overview

Comprehensive unit test suite for GestioneSoci v4.1 covering database operations, backup system, and data validation.

## Test Modules

### test_database.py

**Purpose:** Test database operations and connection management.

**Test Classes:**
- `TestDatabaseBasics` - CRUD operations, table creation
- `TestDatabaseTransactions` - Transaction handling, commit/rollback
- `TestDatabaseConstraints` - Unique constraints, foreign keys, cascades
- `TestDocumentManagement` - Document CRUD operations

**Coverage:**
- Database initialization
- Member CRUD (Create, Read, Update, Delete)
- Soft delete with `deleted_at` timestamp
- Context manager commit/rollback
- Constraint violations (unique, foreign key)
- Cascade delete behavior
- Document management

### test_backup.py

**Purpose:** Test backup system operations.

**Test Classes:**
- `TestBackupBasics` - Incremental backup, hash calculation
- `TestBackupMetadata` - Metadata save/load
- `TestBackupRestore` - Restore operations, safety backups
- `TestBackupList` - Backup listing and validation
- `TestDatabaseUtilities` - Verify, rebuild indexes

**Coverage:**
- SHA256 hash calculation
- Hash-based change detection
- Database integrity verification
- Incremental backup (skip unchanged)
- Force backup override
- Restore with safety backup
- Corrupted backup detection
- Backup listing with validation
- Metadata persistence
- Index rebuild

### test_models.py

**Purpose:** Test Member dataclass validation and serialization.

**Test Classes:**
- `TestMemberCreation` - Basic member creation
- `TestRequiredFields` - Required field validation
- `TestEmailValidation` - Email format and normalization
- `TestCodiceFiscaleValidation` - Codice fiscale format
- `TestCAPValidation` - Postal code validation
- `TestProvinciaValidation` - Province code validation
- `TestDateValidation` - Date format validation
- `TestQuotaValidation` - Quota code validation
- `TestMemberSerialization` - to_dict/from_dict
- `TestHelperFunctions` - Validate and sanitize helpers

**Coverage:**
- Required fields (nome, cognome)
- Email format (RFC 5322) and lowercase normalization
- Codice fiscale (16 alphanumeric uppercase)
- CAP (5 digits)
- Provincia (2 letters uppercase)
- Date fields (ISO YYYY-MM-DD)
- Quota codes (2-3 alphanumeric uppercase)
- to_dict conversion (bool → int)
- from_dict conversion (int → bool)
- Sanitization (trim, normalize)

## Running Tests

### Run All Tests
```bash
python tests/run_tests.py
```

### Run Specific Test Module
```bash
python tests/run_tests.py test_database
python tests/run_tests.py test_backup
python tests/run_tests.py test_models
```

### Run with unittest directly
```bash
# All tests
python -m unittest discover tests/

# Specific module
python -m unittest tests.test_database

# Specific class
python -m unittest tests.test_database.TestDatabaseBasics

# Specific test
python -m unittest tests.test_database.TestDatabaseBasics.test_insert_and_fetch_member
```

## Test Statistics

### test_database.py
- **4 test classes**
- **17+ test methods**
- **Coverage:** Database operations, transactions, constraints, documents

### test_backup.py
- **5 test classes**
- **18+ test methods**
- **Coverage:** Backup, restore, integrity, metadata

### test_models.py
- **10 test classes**
- **40+ test methods**
- **Coverage:** Validation, normalization, serialization

**Total: 75+ tests covering critical functionality**

## Test Isolation

All tests use **temporary files** for isolation:
- `tempfile.NamedTemporaryFile()` for databases
- `tempfile.mkdtemp()` for backup directories
- Automatic cleanup in `tearDown()`

No impact on production data.

## Exception Testing

Tests verify custom exceptions are raised correctly:
- `RequiredFieldError` - Missing required fields
- `InvalidFormatError` - Invalid format
- `DatabaseIntegrityError` - Constraint violations
- `BackupIntegrityError` - Corrupted backups
- `RestoreError` - Failed restore operations

## Validation Testing

Comprehensive validation tests for:
- **Email:** RFC 5322 pattern, normalize to lowercase
- **Codice Fiscale:** 16 chars, alphanumeric, uppercase
- **CAP:** Exactly 5 digits
- **Provincia:** Exactly 2 letters, uppercase
- **Dates:** ISO YYYY-MM-DD format, valid dates
- **Quota Codes:** 2-3 chars, alphanumeric, uppercase

## Transaction Testing

Tests verify proper transaction handling:
- ✅ Commit on success
- ✅ Rollback on error
- ✅ Connection closure in finally block
- ✅ No connection leaks

## Backup Testing

Tests verify backup integrity:
- ✅ SHA256 hash-based change detection
- ✅ Skip backup if DB unchanged
- ✅ Force backup override
- ✅ Safety backup before restore
- ✅ Revert on failed restore
- ✅ Corrupted backup detection

## Future Enhancements

1. **Code Coverage Analysis**
   - Add `coverage.py` to measure test coverage
   - Target: 90%+ coverage

2. **Integration Tests**
   - Test UI integration
   - Test document file operations
   - Test CD meetings workflow

3. **Performance Tests**
   - Benchmark query performance
   - Test with large datasets (10k+ members)
   - Backup performance with large DBs

4. **Mock Testing**
   - Mock file operations
   - Mock external dependencies

## CI/CD Integration

Ready for CI/CD pipelines:
```yaml
# Example GitHub Actions
- name: Run Tests
  run: python tests/run_tests.py
```

Exit code: 0 (success), 1 (failure)

## Troubleshooting

### ImportError
- Ensure `src/` is in `sys.path`
- Check file paths in test imports

### Database Locked
- Tests use isolated temp databases
- Check `tearDown()` cleanup

### Failed Tests
- Run specific test with verbose output
- Check exception messages
- Verify test isolation (no shared state)

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Add tests to appropriate module
3. Update this documentation
4. Run full test suite before committing
