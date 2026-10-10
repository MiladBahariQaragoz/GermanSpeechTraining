from gst.text import content_words, normalise, words


def test_words_lowercases_and_drops_punctuation():
    assert words("Ich möchte Pasta machen.") == ["ich", "möchte", "pasta", "machen"]


def test_words_keeps_contractions_and_skips_dashes():
    assert words("Mir geht's gut – danke!") == ["mir", "geht's", "gut", "danke"]


def test_words_handles_abbreviations_and_eszett():
    assert words("Z. B. eine Straße") == ["z", "b", "eine", "straße"]


def test_content_words_drop_function_words():
    assert content_words("Ich möchte Pasta machen.") == ["möchte", "pasta", "machen"]
    assert content_words("Ich werde die Spaghetti verwenden.") == ["spaghetti", "verwenden"]


def test_normalise_ignores_case_and_punctuation():
    assert normalise("Was wirst du kochen?") == normalise("was wirst du  kochen")
