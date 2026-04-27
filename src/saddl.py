"""
SADDL - The Simple Axiomatic Design Description Language

This file provides some parsing and validation functions for the language.
"""

# Connecting words that help make SADDL more human-readable
prepositions = ["to", "from"]
causal_conjunctions = ["because", "as"]

# This token is only used to indicate the end of a statement when transmitting to/from AERA
# Don't use it anywhere else!
END_OF_STATEMENT = "~~~"


# TODO: Validate statement
def validate_statement(statement):
    return True


# Separate the action and reasoning parts of a statement (used when recording a command)
def statement_to_action_reasoning(statement):
    assert (validate_statement(statement))
    terms = statement.split(" ")

    # Figure out if there's a conjunction in the statement. Ignore repeated instances of a conjunction so
    # we can use 'as', etc. in reasoning statements (ex. "risk should be as low as possible")
    conjunction_idx = 0
    for term in terms:
        if term in causal_conjunctions and conjunction_idx == 0:
            conjunction_idx = terms.index(term)

    # If a conjunction was present, split around that. If not, no reasoning was provided so just return the statement
    if conjunction_idx:
        return " ".join(terms[:conjunction_idx]), " ".join(terms[conjunction_idx + 1:])
    else:
        return statement, "No reasoning"


# Break a statement down and return the individual terms (used when executing a command)
def statement_to_key_terms(statement):
    assert (validate_statement(statement))

    # Start breaking the statement down
    action, reasoning = statement_to_action_reasoning(statement)
    terms = action.split(" ")

    # Extract the specific terms
    if len(terms) == 2:  # VERB OBJECT
        verb, obj = terms
        ind_obj = ""
    elif len(terms) == 4:  # VERB OBJECT to/from INDIRECT_OBJECT
        verb, obj, _, ind_obj = terms
    else:
        raise (Exception("Failed to parse SADDL statement: " + statement))

    return verb, obj, ind_obj, reasoning

# Tokenize a statement for transmission. Here's an example of a tokenized statement:
# ["COUPLE", "FR", "1", ".", "1", "to", "DP", "1", ".", "1", "because", "brakes", "slow", "vehicle", ";"]
# TODO: Generalize this to effect statements
def tokenize(statement):
    tokens = []

    # Break up the statement into key terms
    verb, obj, ind_obj, reasoning = statement_to_key_terms(statement)

    # Verbs are whole tokens
    tokens += [verb]

    # Break objects up into the type of element and the characters of the full degree
    tokens += [obj[:2]]             # Element type (ex. "FR")
    tokens += obj[2:].split()       # Everything else (ex. "1", ".", "2", ".", "3")

    # TODO: Add in conjunctions?

    # If there's an indirect object, add that as well
    if ind_obj:
        tokens += [obj[:2]]         # Element type (ex. "FR")
        tokens += obj[2:].split()   # Everything else (ex. "1", ".", "2", ".", "3")

    # Reasoning goes in word by word
    tokens += reasoning.split(" ")

    # Add in an end of statement token
    tokens += [END_OF_STATEMENT]

    return tokens
