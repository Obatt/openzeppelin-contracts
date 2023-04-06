import "helpers.spec"

methods {
    // library
    add(bytes32)      returns (bool)    envfree
    remove(bytes32)   returns (bool)    envfree
    contains(bytes32) returns (bool)    envfree
    length()          returns (uint256) envfree
    at_(uint256)      returns (bytes32) envfree

    // FV
    _indexOf(bytes32) returns (uint256) envfree
}

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Helpers                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
function sanity() returns bool {
    return length() < max_uint256;
}

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Invariant: All indexed keys are contained                                                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
invariant indexedContained(uint256 index)
    contains(at_(index))
    {
        preserved {
            requireInvariant consistencyIndex(index);
            requireInvariant consistencyIndex(to_uint256(length() - 1));
        }
    }

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Invariant: A value can only be stored at a single location                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
invariant atUniqueness(uint256 index1, uint256 index2)
    index1 == index2 <=> at_(index1) == at_(index2)
    {
        preserved remove(bytes32 key) {
            requireInvariant atUniqueness(index1, to_uint256(length() - 1));
            requireInvariant atUniqueness(index2, to_uint256(length() - 1));
        }
    }

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Invariant: index <> value relationship is consistent                                                                │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
invariant consistencyIndex(uint256 index)
    _indexOf(at_(index)) == index + 1
    {
        preserved remove(bytes32 key) {
            requireInvariant consistencyIndex(to_uint256(length() - 1));
        }
    }

invariant consistencyKey(bytes32 key)
    at_(to_uint256(_indexOf(key) - 1)) == key
    {
        preserved remove(bytes32 otherKey) {
            requireInvariant consistencyKey(otherKey);
            requireInvariant atUniqueness(
                to_uint256(_indexOf(key) - 1),
                to_uint256(_indexOf(otherKey) - 1)
            );
        }
    }

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Rules: state changes                                                                                                │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
rule stateChange(env e, bytes32 key) {
    require sanity();
    requireInvariant consistencyKey(key);

    uint256 lengthBefore   = length();
    bool    containsBefore = contains(key);

    method f; calldataarg args; f(e, args);

    uint256 lengthAfter   = length();
    bool    containsAfter = contains(key);

    assert lengthBefore != lengthAfter => (
        (f.selector == add(bytes32).selector    && lengthAfter == lengthBefore + 1) ||
        (f.selector == remove(bytes32).selector && lengthAfter == lengthBefore - 1)
    );

    assert containsBefore != containsAfter => (
        (f.selector == add(bytes32).selector    && containsAfter) ||
        (f.selector == remove(bytes32).selector && containsBefore)
    );
}

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Rule: at only returns values for index that are in scope.                                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
rule outOfBound(uint256 index) {
    at_@withrevert(index);

    assert lastReverted <=> length() <= index;
}

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Rules: add key to EnumerableSet if not already contained                                                            │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
rule add(bytes32 key, bytes32 otherKey) {
    require sanity();

    uint256 lengthBefore        = length();
    bool    containsBefore      = contains(key);
    bool    containsOtherBefore = contains(otherKey);

    bool added = add@withrevert(key);
    bool success = !lastReverted;

    // liveness & immediate effect
    assert success && contains(key);

    // return value: added iff not contained
    assert added <=> !containsBefore;

    // effect: length increass iff added
    assert length() == lengthBefore + to_uint256(added ? 1 : 0);

    // effect: add at the end
    assert added => at_(lengthBefore) == key;

    // side effect: other keys are not affected
    assert containsOtherBefore != contains(otherKey) => (added && key == otherKey);
}

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Rules: remove key from EnumerableSet if already contained                                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
rule remove(bytes32 key, bytes32 otherKey) {
    requireInvariant consistencyKey(key);
    requireInvariant consistencyKey(otherKey);

    uint256 lengthBefore        = length();
    bool    containsBefore      = contains(key);
    bool    containsOtherBefore = contains(otherKey);

    bool removed = remove@withrevert(key);
    bool success = !lastReverted;

    // liveness & immediate effect
    assert success && !contains(key);

    // return value: removed iff contained
    assert removed <=> containsBefore;

    // effect: length increass iff removed
    assert length() == lengthBefore - to_uint256(removed ? 1 : 0);

    // side effect: other keys are not affected
    assert containsOtherBefore != contains(otherKey) => (removed && key == otherKey);
}

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Rules: when adding a new key, the other keys remain in set, at the same index.                                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
rule atAdd(bytes32 key, uint256 index) {
    require sanity();

    bytes32 atBefore = at_(index);
    add(key);
    bytes32 atAfter = at_@withrevert(index);
    bool atAfterSuccess = !lastReverted;

    assert atAfterSuccess;
    assert atBefore == atAfter;
}

/*
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Rules: when removing a existing key, the other keys remain in set, at the same index (except for the last one).     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
*/
rule atRemove(bytes32 key, uint256 index) {
    uint256 last = to_uint256(length() - 1);

    requireInvariant consistencyKey(key);
    requireInvariant consistencyIndex(index);
    requireInvariant consistencyIndex(last);

    bytes32 atBefore = at_(index);
    bytes32 lastBefore = at_(last);

    remove(key);

    // can't read last value (length decreased)
    bytes32 atAfter = at_@withrevert(index);
    assert lastReverted <=> index == last;

    // One value that is allowed to change is if previous value was removed,
    // in that case the last value before took its place.
    assert (
        index != last &&
        atBefore != atAfter
    ) => (
        atBefore == key &&
        atAfter == lastBefore
    );
}
