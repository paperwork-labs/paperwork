# Chakra v3 imports + theme/testing updates

## What we'll do

- Update Chakra imports to explicit subpackages per v3 across frontend (pages/components/utils).
- Adjust any props/usage per v3 docs where import moves cause type changes.
- Update tests to wrap with ChakraProvider including theme.
- Run formatting (black for backend, maybe prettier/eslint not requested).

## Files to touch

- `frontend/src/**/*.tsx` (Chakra imports/usage)