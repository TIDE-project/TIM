import langcodes
import requests

from timApp.document.translation.language import Language
from timApp.document.translation.translationparser import TranslateApproval, NoTranslate
from timApp.document.translation.translator import (
    RegisteredTranslationService,
    TranslationServiceKey,
    TranslateBlock,
    Usage,
    LanguagePairing,
)
from timApp.timdb.sqa import db
from timApp.user.usergroup import UserGroup
from timApp.util import logger
from timApp.util.flask.requesthelper import NotExist, RouteException


class DeeplTranslationService(RegisteredTranslationService):
    """Translation service using the DeepL (https://www.deepl.com/) API."""

    service_url = db.Column(
        db.Text, default="https://api-free.deepl.com/v2", nullable=False
    )
    """The url base for the API calls (defaults to the free version)."""

    ignore_tag = db.Column(db.Text, default="x", nullable=False)
    """The XML-tag name to use for ignoring pieces of text when XML-handling is
    used.
    """

    headers: dict[str, str]
    """Request-headers needed for authentication with the API-key."""

    source_Language_code: str
    """The source language's code (helps handling regional variants that DeepL
    doesn't differentiate).
    """

    def register(self, user_group: UserGroup) -> None:
        """
        Set headers to use the user group's API-key ready for translation calls.

        :param user_group: The user group whose API key will be used.
        """
        # One key should match one service per one user group TODO is that correct?
        api_key = TranslationServiceKey.query.filter(
            TranslationServiceKey.service_id == self.id,
            TranslationServiceKey.group_id == user_group.id,
        ).all()
        if len(api_key) == 0:
            raise NotExist(
                "Please add a DeepL API key that corresponds the chosen plan into your account"
            )
        if len(api_key) > 1:
            # TODO Does telling this information compromise security in any way?
            raise RouteException(
                "A user should not have more than one (1) API-key per service."
            )
        self.headers = {"Authorization": f"DeepL-Auth-Key {api_key[0].api_key}"}

    # TODO Change the dicts to DeepLTranslateParams and DeeplResponse or smth
    def _post(self, url_slug: str, data: dict | None = None) -> dict:
        """
        Perform an authorized POST-request to the DeepL-API.

        :param url_slug: The last part of URL-path for the API function without
        the starting '/' slash.
        :param data: Data to be transmitted along the request.
        :return: The JSON-response returned by the API.
        """
        resp = requests.post(
            self.service_url + "/" + url_slug, data=data, headers=self.headers
        )

        if resp.ok:
            try:
                return resp.json()
            except requests.exceptions.JSONDecodeError as e:
                raise Exception(f"DeepL API returned malformed JSON: {e}")
        else:
            status_code = resp.status_code

            # Handle the status codes given by DeepL API
            # Using Python 3.10's match-statement would be cool here but Black did not support it

            if status_code == 400:
                debug_exception = Exception(
                    f"The request to the DeepL API was bad. Please check your parameters."
                )
            elif status_code == 403:
                debug_exception = Exception(
                    f"Authorization failed. Please check your DeepL API key for typos."
                )
            elif status_code == 404:
                debug_exception = Exception(
                    f"The requested translator could not be found. Please try again later."
                )
            elif status_code == 413:
                debug_exception = Exception(
                    f"The request size exceeds the API's limit. Please try again with a smaller document."
                )
            elif status_code == 414:
                debug_exception = Exception(
                    f"The request URL is too long. Please contact TIM support."
                )
            elif status_code == 429:
                debug_exception = Exception(
                    f"Too many requests were sent. Please wait and resend the request later."
                )
            elif status_code == 456:
                debug_exception = Exception(
                    f"You have exceeded your character quota. Please try again when your quota has reset."
                )
            elif status_code == 503:
                debug_exception = Exception(
                    f"Translator currently unavailable. Please try again later."
                )
            elif status_code == 529:
                debug_exception = Exception(
                    f"Too many requests were sent. Please wait and resend the request later."
                )
            elif status_code >= 500 & status_code < 600:
                debug_exception = Exception(
                    f"An internal error occurred on the DeepL server. Please try again."
                )
            else:
                debug_exception = Exception(
                    f"DeepL API / {url_slug} responded with {resp.status_code}"
                )

            raise RouteException(
                description="The request failed. Error message: " + str(debug_exception)
            )

    def _translate(
        self,
        text: list[str],
        source_lang: str | None,
        target_lang: str,
        *,
        split_sentences: str | None = None,
        preserve_formatting: str | None = None,
        tag_handling: str | None = None,
        non_splitting_tags: list[str] = [],
        splitting_tags: list[str] = [],
        ignore_tags: list[str] = [],
    ) -> dict:
        """
        Supports most of the parameters of a DeepL API translate call.
        See https://www.deepl.com/docs-api/translating-text/request/ for valid
        parameter values and more information.

        :param text: Text to translate that can contain XML.
        :param source_lang: Language of the text.
        :param target_lang: Language to translate the text into.
        :param split_sentences: Is text split before translation.
        :param preserve_formatting: Is formatting preserved during translation.
        :param tag_handling: XML and HTML are currently supported.
        :param non_splitting_tags: Tags that never split sentences (eg. for the
        tag "<x>" the parameter should be "x").
        :param splitting_tags: Tags that always split sentences.
        :param ignore_tags: Tags to ignore when translating.
        :return: The DeepL API response JSON.
        """

        src_lang = source_lang

        if source_lang is not None and (
            source_lang.lower() == "en-gb" or source_lang.lower() == "en-us"
        ):
            src_lang = "en"

        logger.log_info(f"Amount of separate translatable texts: {str(len(text))}/50")

        data = {
            "text": text,
            "source_lang": src_lang,
            "target_lang": target_lang,
            "split_sentences": split_sentences,
            "preserve_formatting": preserve_formatting,
            "tag_handling": tag_handling,
            "non_splitting_tags": ",".join(non_splitting_tags),
            "splitting_tags": ",".join(splitting_tags),
            "ignore_tags": ",".join(ignore_tags),
        }

        return self._post("translate", data)

    # TODO Cache this
    def _languages(self, *, is_source: bool) -> dict:
        """
        Get languages supported by the API.

        :param is_source: Flag to query for supported source-languages.
        :return: Languages supported in translations by type (source or target).
        """
        return self._post(
            "languages", data={"type": "source" if is_source else "target"}
        )

    def preprocess(self, elem: TranslateApproval) -> None:
        """
        Protect the text inside element from mangling in translation by adding
        XML-tags.

        :param elem: The element to add XML-protection-tags to.
        :return None. The tag is added to the input object.
        """
        # TODO If the protection tag is found in the content text, somehow encode such tag first
        if type(elem) is NoTranslate:
            elem.text = f"<{self.ignore_tag}>{elem.text}</{self.ignore_tag}>"

    def postprocess(self, text: str) -> str:
        """
        Remove unnecessary protection tags from the text.

        :param text: The text to remove XML-protection-tags from.
        :return: Text without the previously added protecting XML-tags.
        """
        return text.replace(f"<{self.ignore_tag}>", "").replace(
            f"</{self.ignore_tag}>", ""
        )

    def translate(
        self,
        texts: list[TranslateBlock],
        source_lang: Language | None,
        target_lang: Language,
        tag_handling: str = "xml",
    ) -> list[str]:
        """
        Use the DeepL API to translate text between languages.

        :param texts: Text to be translated
        :param source_lang: Language of input text. None value makes DeepL
        guess it from the text.
        :param target_lang: Language for target language.
        :param tag_handling: See comment in superclass.
        :return: List of strings in target language with the non-translatable
        parts intact.
        """
        source_lang_code = source_lang.lang_code if source_lang else None

        # Get the translatable text of objects and add XML-tag -protection to them if so needed
        if tag_handling == "xml":
            # TODO This multidimensionalism of lists is hard to read
            for block in texts:
                for elem in block:
                    self.preprocess(elem)
        # TODO This multidimensionalism of lists is hard to read
        # Combine the strings of each block for maximum-effectiveness of the translation-call.
        protected_texts = list(
            map(lambda xs: "".join(map(lambda x: x.text, xs)), texts)
        )

        # Translate texts 50 at a time to match DeepL-spec:
        # "Up to 50 text parameters can be submitted in one request."
        # https://www.deepl.com/docs-api/translating-text/large-volumes/
        translation_resps = list()
        for i in range(0, len(protected_texts), 50):
            resp_json = self._translate(
                protected_texts[i : i + 50],
                # Send uppercase, because it is used in DeepL documentation
                source_lang_code.upper(),
                target_lang.lang_code.upper(),
                split_sentences="1",  # "1" (for example) keeps original document's empty newlines
                # NOTE Preserve formatting=1 might remove punctuation
                preserve_formatting="0",  # "1" DeepL does not make guesses of the desired sentence
                tag_handling=tag_handling,
                ignore_tags=[self.ignore_tag],
            )
            translation_resps += resp_json["translations"]

        # Insert the text-parts sent to the API into correct places in original elements
        translated_texts = list()
        for resp in translation_resps:
            clean_block = (
                self.postprocess(resp["text"])
                if tag_handling == "xml"
                else resp["text"]
            )
            translated_texts.append(clean_block)
        return translated_texts

    def usage(self) -> Usage:
        resp_json = self._post("usage")
        return Usage(
            character_count=int(resp_json["character_count"]),
            character_limit=int(resp_json["character_limit"]),
        )

    def get_languages(self, source_langs: bool) -> list[Language]:
        """
        Fetches the source or target languages from DeepL.

        :param source_langs: Whether source languages must be fetched
        :return: The list of source of target languages from DeepL.
        """

        def get_langs_from_db(deepl_lang: dict) -> Language | None:
            try:
                language = deepl_lang["language"]
                code = langcodes.get(language).to_tag()

                # This is needed because DeepL's source languages only include English (EN) and not regional variants
                if code.lower() == "en":
                    code = self.source_Language_code
                return Language.query_by_code(code)
            except LookupError:
                return None

        self.source_Language_code = "en-GB"
        langs = self._languages(is_source=source_langs)
        return_langs = list(filter(None, map(get_langs_from_db, langs)))
        if source_langs:
            self.source_Language_code = "en-US"
            en: Language | None = Language(
                flag_uri="",
                lang_code="",
                lang_name="",
                autonym="",
            )
            for lang in langs:
                if lang.get("language").lower() == "en":
                    en = get_langs_from_db(lang)
            if en is not None:
                return_langs = return_langs + [en]
        return return_langs

    # TODO Cache this maybe?
    def languages(self) -> LanguagePairing:
        """
        Asks the DeepL API for the list of supported languages (Note: the
        supported language pairings are not explicitly specified) and turns the
        returned language codes to Languages found in the database.

        :return: Dictionary of source langs to lists of target langs, that are
        supported by the API and also found in database.
        """

        def get_lang(deepl_lang: dict) -> Language | None:
            try:
                language = deepl_lang["language"]
                code = langcodes.get(language).to_tag()

                # This is needed because DeepL's source languages only include English (EN) and not regional variants
                if code.lower() == "en":
                    code = self.source_Language_code
                return Language.query_by_code(code)
            except LookupError:
                return None

        # Query API for supported source and target languages and transform them into suitable format
        resp_json_src = self._languages(is_source=True)
        resp_json_target = self._languages(is_source=False)
        db_langs_src: list[Language] = list(filter(None, map(get_lang, resp_json_src)))
        db_langs_target: list[Language] = list(
            filter(None, map(get_lang, resp_json_target))
        )
        langs_map = {lang.lang_code: db_langs_target for lang in db_langs_src}
        return LanguagePairing(langs_map)

    def supports(self, source_lang: Language, target_lang: Language) -> bool:
        """
        Check that the source language can be translated into target language
        by the translation API.

        :param source_lang: Language of original text
        :param target_lang: Language to translate into
        :return: True, if the pairing is supported
        """

        self.source_Language_code = source_lang.lang_code

        try:
            supported_languages: list[Language] = self.languages()[
                self.source_Language_code
            ]
        except KeyError as e:
            raise RouteException(
                f"The language code {e} was not found in supported source languages."
            )

        # The target language is found by the primary key
        # TODO is this too much? Can't strings be just as good?
        #  Maybe better would be to handle Languages by their database id's?
        return any(x.lang_code == target_lang.lang_code for x in supported_languages)

    def supports_tag_handling(self, tag_type: str) -> bool:
        return tag_type in ["xml", "html"]

    # TODO Make the value an enum like with Verification?
    __mapper_args__ = {"polymorphic_identity": "DeepL Free"}


class DeeplProTranslationService(DeeplTranslationService):
    # TODO Make the value an enum like with Verification?
    __mapper_args__ = {"polymorphic_identity": "DeepL Pro"}
