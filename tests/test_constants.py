from utils import constants


def test_link_message_appends_the_url_when_configured():
    assert constants.link_message("Contact", "https://example.test/c") == "Contact:\nhttps://example.test/c"


def test_link_message_is_a_plain_sentence_without_a_url():
    assert constants.link_message("Contact", "") == "Contact."


def test_configured_links_appear_in_user_messages():
    assert constants.PRIVACY_URL == "https://example.test/privacy"
    assert constants.CONTACT_URL == "https://example.test/contact"
    assert constants.PRIVACY_URL in constants.START_MESSAGE_TEMPLATE
    assert constants.PRIVACY_URL in constants.PRIVACY_MESSAGE
    assert constants.CONTACT_URL in constants.CONTACT_MESSAGE
    assert constants.CONTACT_URL in constants.QUOTA_EXTENSION_MESSAGE


def test_every_privacy_text_carries_the_ai_notice():
    assert constants.AI_NOTICE in constants.START_MESSAGE_TEMPLATE
    assert constants.AI_NOTICE in constants.PRIVACY_MESSAGE
