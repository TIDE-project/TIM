// TODO: save cursor position when changing editor

import angular, {IController, IPromise, IRootElementService, IScope} from "angular";
import $ from "jquery";
import rangyinputs from "rangyinputs";
import {timApp} from "tim/app";
import * as draggable from "tim/directives/draggable";
import {setEditorScope} from "tim/editorScope";
import sessionsettings from "tim/session";
import {markAsUsed, setSetting} from "tim/utils";
import {IAceEditor} from "../ace-types";
import {getActiveDocument} from "../controllers/view/document";
import {isSettings} from "../controllers/view/parhelpers";
import {showMessageDialog} from "../dialog";
import {Duplicate} from "../edittypes";
import {$compile, $http, $localStorage, $log, $timeout, $upload, $window} from "../ngimport";
import {IPluginInfoResponse, ParCompiler} from "../services/parCompiler";
import {AceParEditor} from "./AceParEditor";
import {TextAreaParEditor} from "./TextAreaParEditor";
import {DraggableController} from "./draggable";

markAsUsed(draggable, rangyinputs);

const MENU_BUTTON_CLASS = "menuButtons";
const MENU_BUTTON_CLASS_DOT = "." + MENU_BUTTON_CLASS;
const CURSOR = "⁞";

export class PareditorController implements IController {
    private static $inject = ["$scope", "$element"];
    private afterDelete: (params: { extraData: {}, saveData: {} }) => void;
    private afterCancel: (params: { extraData: {} }) => void;
    private afterSave: (params: { extraData: {}, saveData: {} }) => void;
    private data: { original_par: any };
    private dataLoaded: boolean;
    private deleteUrl: string;
    private deleting: boolean;
    private duplicates: Duplicate[];
    private editor: TextAreaParEditor | AceParEditor;
    private element: JQuery;
    private extraData: {
        attrs: { classes: string[], [i: string]: any },
        docId: number,
        par: string,
        access: string,
        tags: { markread: boolean },
        isComment: boolean,
    };
    private file: File & { progress?: number, error?: string };
    private initialText: string;
    private initialTextUrl: string;
    private inputs: JQuery[];
    private isIE: boolean;
    private lstag: string;
    private minSizeSet: boolean;
    private newAttr: string;
    private newPars: string[];
    private oldmeta: HTMLMetaElement;
    private wrap: { n: number };
    private options: {
        localSaveTag: string,
        texts: {
            initialText: string;
        },
        showDelete: boolean,
        showPlugins: boolean,
        showSettings: boolean,
        destroyAfterSave: boolean,
        touchDevice: boolean,
        metaset: boolean,
    };
    private originalPar: any;
    private outofdate: boolean;
    private parCount: number;
    private pluginButtonList: { [tabName: string]: JQuery[] };
    private pluginRenameForm: any;
    private previewReleased: boolean;
    private previewUrl: string;
    private proeditor: boolean;
    private renameFormShowing: boolean;
    private saveUrl: string;
    private saving: boolean;
    private scrollPos: number;
    private tables: {
        normal: string,
        example: string,
        noheaders: string,
        multiline: string,
        strokes: string,
        pipe: string,
    };
    private timer?: IPromise<void>;
    private unreadUrl: string;
    private uploadedFile: string;
    private scope: IScope;
    private storage: Storage;
    private touchDevice: boolean;
    private plugintab: JQuery;
    private autocomplete: boolean;
    private citeText: string;
    private draggable: DraggableController | undefined;
    private docSettings: { macros: { dates: string[], knro: number, stampformat: string } };

    constructor(scope: IScope, element: IRootElementService) {
        this.element = element;
        this.options.showSettings = false;
        this.scope = scope;
        this.lstag = this.options.localSaveTag || ""; // par/note/addAbove
        this.storage = localStorage;

        const sn = this.storage.getItem("wrap" + this.lstag);
        let n = parseInt(sn || "-90");
        if (isNaN(n)) {
            n = -90;
        }

        this.wrap = {n: n};

        this.proeditor = this.getLocalBool("proeditor", this.lstag === "par");
        this.autocomplete = this.getLocalBool("autocomplete", false);

        this.pluginButtonList = {};

        if ((navigator.userAgent.match(/Trident/i))) {
            this.isIE = true;
        }

        this.dataLoaded = false; // allow load in first time what ever editor

        this.element.find(".editorContainer").on("resize", () => this.adjustPreview());

        this.citeText = this.getCiteText();

        this.tables = {

            normal: "Otsikko1 Otsikko2 Otsikko3 Otsikko4\n" +
            "-------- -------- -------- --------\n" +
            "1.rivi   x        x        x       \n" +
            "2.rivi   x        x        x       ",

            example: "Table:  Otsikko taulukolle\n\n" +
            "Otsikko    Vasen laita    Keskitetty    Oikea laita\n" +
            "---------- ------------- ------------ -------------\n" +
            "1. rivi      2                  3         4\n" +
            "2. rivi        1000      2000             30000",

            noheaders: ":  Otsikko taulukolle\n\n" +
            "---------- ------------- ------------ -------------\n" +
            "1. rivi      2                  3         4\n" +
            "2. rivi        1000      2000             30000\n" +
            "---------- ------------- ------------ -------------\n",

            multiline: "Table:  Otsikko taulukolle voi\n" +
            "jakaantua usealle riville\n\n" +
            "-----------------------------------------------------\n" +
            "Ekan       Toisen\         kolmas\            neljäs\\\n" +
            "sarkkeen   sarakkeen\     keskitettynä      oikeassa\\\n" +
            "otsikko    otsikko                           reunassa\n" +
            "---------- ------------- -------------- -------------\n" +
            "1. rivi     toki\              3         4\n" +
            "voi olla    sisältökin\n" +
            "useita        voi\\\n" +
            "rivejä      olla \n" +
            "            monella\\\n" +
            "            rivillä\n" +
            "            \n" +
            "2. rivi        1000      2000             30000\n" +
            "-----------------------------------------------------\n",
            strokes: ": Viivoilla tehty taulukko\n\n" +
            "+---------------+---------------+----------------------+\n" +
            "| Hedelmä       | Hinta         | Edut                 |\n" +
            "+===============+===============+======================+\n" +
            "| Banaani       |  1.34 €       | - valmis kääre       |\n" +
            "|               |               | - kirkas väri        |\n" +
            "+---------------+---------------+----------------------+\n" +
            "| Appelsiini    |  2.10 €       | - auttaa keripukkiin |\n" +
            "|               |               | - makea              |\n" +
            "+---------------+---------------+----------------------+\n",

            pipe: ": Taulukko, jossa tolpat määräävat sarkkeiden paikat.\n\n" +
            "|Oikea  | Vasen | Oletus | Keskitetty |\n" +
            "|------:|:-----|---------|:------:|\n" +
            "|   12  |  12  |    12   |    12  |\n" +
            "|  123  |  123 |   123   |   123  |\n" +
            "|    1  |    1 |     1   |     1  |\n",
        };

        $(document).on("webkitfullscreenchange mozfullscreenchange fullscreenchange MSFullscreenChange", (event) => {
            const editor = $(element).find("#pareditor").get(0);
            const doc: any = document;
            if (!doc.fullscreenElement &&    // alternative standard method
                !doc.mozFullScreenElement && !doc.webkitFullscreenElement && !doc.msFullscreenElement) {
                editor.removeAttribute("style");
            }
        });

        this.outofdate = false;
        this.parCount = 0;
        this.touchDevice = false;

        if (this.options.touchDevice) {
            if (!this.options.metaset) {
                const $meta = $("meta[name='viewport']");
                this.oldmeta = $meta[0] as HTMLMetaElement;
                $meta.remove();
                $("head").prepend('<meta name="viewport" content="width=device-width, height=device-height, initial-scale=1, maximum-scale=1, user-scalable=0">');
            }
            this.options.metaset = true;
        }

        const scrollTop = $(window).scrollTop() || 0;
        const height = $(window).height() || 500;
        const viewport = {
            bottom: scrollTop + height,
            top: scrollTop,
        };
        const offset = element.offset() || {top: 0};
        const outerHeight = element.outerHeight() || 200;
        const bounds = {
            bottom: offset.top + outerHeight,
            top: offset.top,
        };
        if (bounds.bottom > viewport.bottom || bounds.top < viewport.top) {
            $("html, body").scrollTop(offset.top);
        }
    }

    $onInit() {
        const oldMode = $window.localStorage.getItem("oldMode" + this.options.localSaveTag) || (this.options.touchDevice ? "text" : "ace");
        this.changeEditor(oldMode);
        this.scope.$watch(() => this.autocomplete, () => {
            if (this.isAce(this.editor)) {
                this.setLocalValue("autocomplete", this.autocomplete.toString());
                this.editor.setAutoCompletion(this.autocomplete);
            }
        });
        this.docSettings = $window.docSettings;
    }

    $postLink() {
        this.plugintab = this.element.find("#pluginButtons");
        this.getPluginsInOrder();

        if (sessionsettings.editortab) {
            const tab = sessionsettings.editortab.substring(0, sessionsettings.editortab.lastIndexOf("Buttons"));
            const tabelement = this.element.find("#" + tab);
            if (tabelement.length) {
                this.setActiveTab(tabelement, sessionsettings.editortab);
            }
        }
    }

    $onDestroy() {
        setEditorScope(null);
    }

    getCiteText(): string {
        return `#- {rd="${this.extraData.docId}" rl="no" rp="${this.extraData.par}"}`;
    }

    selectAllText(evt: Event) {
        (evt.target as HTMLInputElement).select();
    }

    getLocalBool(name: string, def: boolean): boolean {
        let ret = def;
        if (!ret) {
            ret = false;
        }
        const val = this.storage.getItem(name + this.lstag);
        if (!val) {
            return ret;
        }
        return val === "true";
    }

    setLocalValue(name: string, val: string) {
        $window.localStorage.setItem(name + this.lstag, val);
    }

    setEditorMinSize() {
        const editor = this.element;
        this.previewReleased = false;

        const editorOffsetStr = this.storage.getItem("editorReleasedOffset" + this.lstag);
        if (editorOffsetStr) {
            const editorOffset = JSON.parse(editorOffsetStr);
            const offset = editor.offset();
            if (offset) {
                editor.css("left", editorOffset.left - offset.left);
            }
        }

        if (this.storage.getItem("previewIsReleased" + this.lstag) === "true") {
            this.releaseClicked();
        }
        this.minSizeSet = true;
    }

    deleteAttribute(key: string) {
        delete this.extraData.attrs[key];
    }

    deleteClass(classIndex: number) {
        this.extraData.attrs.classes.splice(classIndex, 1);
    }

    addClass() {
        this.extraData.attrs.classes.push("");
    }

    addAttribute() {
        if (this.newAttr === "classes") {
            this.extraData.attrs[this.newAttr] = [];
        } else {
            this.extraData.attrs[this.newAttr] = "";
        }
        this.newAttr = "";
    }

    /*
Template format is either the old plugin syntax:

    {
        'text' : ['my1', 'my2'],      // list of tabs firts
        'templates' : [               // and then array of arrays of items
            [
                {'data': 'cat', 'expl': 'Add cat', 'text': 'Cat'},
                {'data': 'dog', 'expl': 'Add dog'},
            ],
            [
                {'data': 'fox', 'expl': 'Add fox', 'text': 'Fox'},
            ]
        ]
    }

or newer one that is more familiar to write in YAML:

    {
        'templates' :
          { 'my1':  // list of objects where is the name of tab as a key
            [
                {'data': 'cat', 'expl': 'Add cat', 'text': 'Cat'},
                {'data': 'dog', 'expl': 'Add dog'},
            ]
           ,
           'my2':  // if only one, does not need to be array
                {'data': 'fox', 'expl': 'Add fox', 'text': 'Fox'},
          }
    }

 */
    getPluginsInOrder() {
        for (const plugin in $window.reqs) {
            if ($window.reqs.hasOwnProperty(plugin)) {
                const data = $window.reqs[plugin];
                if (data.templates) {
                    const isobj = !(data.templates instanceof Array);
                    let tabs = data.text || [plugin];
                    if (isobj) tabs = Object.keys(data.templates);
                    const len = tabs.length;
                    for (let j = 0; j < len; j++) {
                        const tab = tabs[j];
                        let templs = null;
                        if (isobj) {
                            templs = data.templates[tab];
                        } else {
                            templs = data.templates[j];
                        }
                        if (!(templs instanceof Array)) templs = [templs];
                        if (!this.pluginButtonList[tab]) {
                            this.pluginButtonList[tab] = [];
                        }
                        for (let k = 0; k < templs.length; k++) {
                            let template = templs[k];
                            if (!(template instanceof Object))
                                template = {text: template, data: template};
                            const text = (template.text || template.file || template.data);
                            const tempdata = (template.data || null);
                            let clickfn;
                            if (tempdata)
                                clickfn = `$ctrl.putTemplate('${tempdata}')`;
                            else
                                clickfn = `$ctrl.getTemplate('${plugin}','${template.file}', '${j}')`;
                            this.pluginButtonList[tab].push(this.createMenuButton(text, template.expl, clickfn));
                        }
                    }
                }
            }
        }

        for (const key in this.pluginButtonList) {
            if (this.pluginButtonList.hasOwnProperty(key)) {
                const clickfunction = "$ctrl.pluginClicked($event, '" + key + "')";
                const button = $("<button>", {
                    "class": "editorButton",
                    "text": key,
                    "title": key,
                    "ng-click": clickfunction,
                });
                this.plugintab.append($compile(button)(this.scope));
            }
        }

        const help = $("<a>", {
            "class": "helpButton",
            "text": "[?]",
            "title": "Help for plugin attributes",
            "onclick": "window.open('https://tim.jyu.fi/view/tim/ohjeita/csPlugin', '_blank')"
        });
        this.plugintab.append($compile(help)(this.scope));
    }

    async setInitialText() {
        if (this.dataLoaded) return;
        if (!this.initialTextUrl) {
            var initialText = "";
            if (this.options.texts) initialText = this.options.texts.initialText;
            if (initialText) {
                var pos = initialText.indexOf(CURSOR);
                if (pos >= 0) initialText = initialText.replace(CURSOR, ""); // cursor pos
                this.editor.setEditorText(initialText);
                this.initialText = initialText;
                angular.extend(this.extraData, {});
                this.editorChanged();
                $timeout(() => {
                    if (pos >= 0) this.editor.setPosition(pos);
                }, 10);
            }
            this.dataLoaded = true;
            return;
        }
        this.editor.setEditorText("Loading text...");
        this.dataLoaded = true; // prevent data load in future
        const response = await $http.get<{ text: string, extraData: any }>(this.initialTextUrl, {
            params: this.extraData,
        });
        const data = response.data;
        this.editor.setEditorText(data.text);
        this.initialText = data.text;
        if (isSettings(data.text)) {
            this.options.showPlugins = false;
            this.options.showSettings = true;
        }
        angular.extend(this.extraData, data.extraData);
        this.editorChanged();
    }

    adjustPreview() {
        window.setTimeout(() => {
            const $editor = this.element;
            const $previewContent = this.element.find(".previewcontent");
            const previewDiv = this.element.find("#previewDiv");
            // If preview is released make sure that preview doesn't go out of bounds
            if (this.previewReleased) {
                const previewOffset = previewDiv.offset();
                if (!previewOffset) {
                    return;
                }
                const newOffset = previewOffset;
                if (previewOffset.top < 0 /*|| previewOffset.top > $window.innerHeight */) {
                    newOffset.top = 0;
                }
                if (previewOffset.left < 0 || previewOffset.left > $window.innerWidth) {
                    newOffset.left = 0;
                }
                previewDiv.offset(newOffset);
            }
            // Check that editor doesn't go out of bounds
            const editorOffset = $editor.offset();
            if (!editorOffset) {
                return;
            }
            const newOffset = editorOffset;
            if (editorOffset.top < 0) {
                newOffset.top = 0;
            }
            if (editorOffset.left < 0) {
                newOffset.left = 0;
            }
            $editor.offset(newOffset);
            $previewContent.scrollTop(this.scrollPos);
        }, 25);

    }

    createTextArea(text: string) {
        if (!this.minSizeSet) {
            this.setEditorMinSize();
        }
        const $textarea = $(`
<textarea rows="10"
      id="teksti"
      wrap="off">
</textarea>`);
        this.element.find(".editorContainer").append($textarea);
        this.editor = new TextAreaParEditor(this.element.find("#teksti"), {
            wrapFn: () => this.wrapFn(),
            saveClicked: () => this.saveClicked(),
            getWrapValue: () => this.wrap.n,
        });
        this.editor.setEditorText(text);
        $textarea.on("input", () => this.editorChanged());
    }

    editorReady() {
        this.editor.focus();
        this.editor.bottomClicked();
        this.element.find(".editorContainer").removeClass("editor-loading");
    }

    editorChanged() {
        this.scope.$evalAsync(() => {
            this.outofdate = true;
            if (this.timer) {
                $timeout.cancel(this.timer);
            }

            this.timer = $timeout(() => {
                const text = this.editor.getEditorText();
                this.scrollPos = this.element.find(".previewcontent").scrollTop() || this.scrollPos;
                $http.post<IPluginInfoResponse>(this.previewUrl, angular.extend({
                    text,
                }, this.extraData)).then(async (response) => {
                    const data = response.data;
                    const compiled = await ParCompiler.compile(data, this.scope);
                    const $previewDiv = angular.element(".previewcontent");
                    $previewDiv.empty().append(compiled);
                    this.outofdate = false;
                    this.parCount = $previewDiv.children().length;
                    this.element.find(".editorContainer").resize();
                }, (response) => {
                    $window.alert("Failed to show preview: " + response.data.error);
                });
                this.outofdate = true;
            }, 500);
        });
    }

    wrapFn(func: (() => void) | null = null) {
        if (!this.touchDevice) {
            // For some reason, on Chrome, re-focusing the editor messes up scroll position
            // when clicking a tab and moving mouse while clicking, so
            // we save and restore it manually.
            const s = $(window).scrollTop();
            this.editor.focus();
            $(window).scrollTop(s || this.scrollPos);
        }
        if (func != null) {
            func();
        }
        if (this.isIE) {
            this.editorChanged();
        }
    }

    changeMeta() {
        $("meta[name='viewport']").remove();
        const $meta = $(this.oldmeta);
        $("head").prepend($meta);
    }

    deleteClicked() {
        if (!this.options.showDelete) {
            this.cancelClicked(); // when empty and save clicked there is no par
            return;
        }
        if (this.deleting) {
            return;
        }
        if (!$window.confirm("Delete - are you sure?")) {
            return;
        }
        this.deleting = true;

        $http.post(this.deleteUrl, this.extraData).then((response) => {
            const data = response.data;
            this.afterDelete({
                extraData: this.extraData,
                saveData: data,
            });
            if (this.options.destroyAfterSave) {
                this.destroy();
            }
            this.deleting = false;
        }, (response) => {
            $window.alert("Failed to delete: " + response.data.error);
            this.deleting = false;
        });
        if (this.options.touchDevice) {
            this.changeMeta();
        }
    }

    destroy() {
        this.element.remove();
        if (this.draggable) {
            this.draggable.$destroy();
        }
    }

    showUnread() {
        return this.extraData.par !== "NEW_PAR" && this.element.parents(".par").find(".readline.read").length > 0;
    }

    unreadClicked() {
        if (this.options.touchDevice) {
            this.changeMeta();
        }
        $http.put(this.unreadUrl + "/" + this.extraData.par, {}).then((response) => {
            this.element.parents(".par").find(".readline").removeClass("read read-modified");
            if (this.initialText === this.editor.getEditorText()) {
                this.destroy();
                this.afterCancel({
                    extraData: this.extraData,
                });
            }
            getActiveDocument().refreshSectionReadMarks();
        }, (response) => {
            $log.error("Failed to mark paragraph as unread");
        });
    }

    cancelClicked() {
        if (this.options.touchDevice) {
            this.changeMeta();
        }
        this.destroy();
        this.afterCancel({
            extraData: this.extraData,
        });
    }

    releaseClicked() {
        const div = this.element.find("#previewDiv");
        const content = this.element.find(".previewcontent");
        const editor = this.element;
        this.previewReleased = !(this.previewReleased);
        const tag = this.options.localSaveTag || "";
        const storage = $window.localStorage;

        const releaseBtn = document.getElementById("releaseButton");
        if (!releaseBtn) {
            showMessageDialog("Failed to release preview; button not found");
            return;
        }
        if (div.css("position") === "absolute") {
            // If preview has been clicked back in, save the preview position before making it static again
            if (this.minSizeSet) {
                this.savePreviewData(true);
            }
            div.css("position", "static");
            div.find(".draghandle").css("display", "none");
            content.css("max-width", "");
            div.css("display", "default");
            editor.css("overflow", "hidden");
            content.css("max-height", "40vh");
            content.css("overflow-x", "");
            content.css("width", "");
            div.css("padding", 0);
            releaseBtn.innerHTML = "&#8594;";
        } else {
            const currDivOffset = div.offset();
            const winWidth = $(window).width();
            const divWidth = div.width();
            const editorOffset = editor.offset();
            const editorWidth = editor.width();
            if (!currDivOffset || !winWidth || !divWidth || !editorOffset || !editorWidth) {
                return;
            }
            // If preview has just been released or it was released last time editor was open
            if (this.minSizeSet || storage.getItem("previewIsReleased" + tag) === "true") {
                const storedOffset = storage.getItem("previewReleasedOffset" + tag);

                if (storedOffset) {
                    const savedOffset = JSON.parse(storedOffset);
                    currDivOffset.left = editorOffset.left + savedOffset.left;
                    currDivOffset.top = editorOffset.top + savedOffset.top;
                } else {

                    if (winWidth < editorWidth + divWidth) {
                        currDivOffset.top += 5;
                        currDivOffset.left += 5;
                    } else {
                        currDivOffset.top = editorOffset.top;
                        currDivOffset.left = editorOffset.left + editorWidth + 3;
                    }
                }
            }
            div.css("position", "absolute");
            editor.css("overflow", "visible");
            div.find(".draghandle").css("display", "block");
            div.css("display", "table");
            div.css("width", "100%");
            div.css("padding", 5);
            const height = window.innerHeight - 90;
            content.css("max-height", height);
            content.css("max-width", window.innerWidth - 90);
            content.css("overflow-x", "auto");
            releaseBtn.innerHTML = "&#8592;";
            div.offset(currDivOffset);
        }
        this.adjustPreview();
    }

    savePreviewData(savePreviewPosition: boolean) {
        const tag = this.options.localSaveTag || "";
        const storage = $window.localStorage;
        const editorOffset = this.element.offset();
        storage.setItem("editorReleasedOffset" + tag, JSON.stringify(editorOffset));
        if (savePreviewPosition) {
            // Calculate distance from editor's top and left
            const previewOffset = this.element.find("#previewDiv").offset();
            if (previewOffset && editorOffset) {
                const left = previewOffset.left - editorOffset.left;
                const top = previewOffset.top - editorOffset.top;
                storage.setItem("previewReleasedOffset" + tag, JSON.stringify({left, top}));
            }
        }
        storage.setItem("previewIsReleased" + tag, this.previewReleased.toString());
    }

    /**
     * Called when user wants to cancel changes after entering duplicate task-ids
     */
    cancelPluginRenameClicked() {
        // Cancels recent changes to paragraph/document
        $http.post("/cancelChanges/", angular.extend({
            newPars: this.newPars,
            originalPar: this.originalPar,
            docId: this.extraData.docId,
            parId: this.extraData.par,
        }, this.extraData)).then((response) => {
            // Remove the form and return to editor
            this.element.find("#pluginRenameForm").get(0).remove();
            this.renameFormShowing = false;
            this.saving = false;
            this.deleting = false;
        }, (response) => {
            $window.alert("Failed to cancel save: " + response.data.error);
        });
    }

    /**
     * Function that handles different cases of user input in plugin rename form
     * after user has saved multiple plugins with the same taskname
     * @param inputs - The input fields in plugin rename form
     * @param duplicates - The duplicate tasks, contains duplicate taskIds and relevant parIds
     * @param renameDuplicates - Whether user wants to rename task names or not
     */
    renameTaskNamesClicked(inputs: JQuery[], duplicates: Duplicate[], renameDuplicates = false) {
        // If user wants to ignore duplicates proceed like normal after saving
        if (!renameDuplicates) {
            this.renameFormShowing = false;
            if (this.options.destroyAfterSave) {
                this.afterSave({
                    extraData: this.extraData,
                    saveData: this.data,
                });
                this.destroy();
                return;
            }
        }
        const duplicateData = [];
        let duplicate;

        // if duplicates are to be renamed automatically (user pressed "rename automatically")
        if (typeof inputs === "undefined") {
            if (renameDuplicates) {
                if (duplicates.length > 0) {
                    for (let i = 0; i < duplicates.length; i++) {
                        duplicate = [];
                        duplicate.push(duplicates[i][0]);
                        duplicate.push("");
                        duplicate.push(duplicates[i][1]);
                        duplicateData.push(duplicate);
                    }
                }
            }
        } else {
            // use given names from the input fields
            for (let j = 0; j < duplicates.length; j++) {
                duplicate = [];
                duplicate.push(duplicates[j][0]);
                duplicate.push((inputs[j][0] as HTMLInputElement).value);
                duplicate.push(duplicates[j][1]);
                duplicateData.push(duplicate);
            }
        }
        // Save the new task names for duplicates
        $http.post<{ duplicates: Duplicate[] }>("/postNewTaskNames/", angular.extend({
            duplicates: duplicateData,
            renameDuplicates,
        }, this.extraData)).then((response) => {
            const data = response.data;
            // If no new duplicates were founds
            if (data.duplicates.length <= 0) {
                this.renameFormShowing = false;
                this.afterSave({
                    extraData: this.extraData,
                    saveData: this.data,
                });
                if (this.options.destroyAfterSave) {
                    this.destroy();
                }
            }
            // If there still are duplicates remake the form
            if (data.duplicates.length > 0) {
                this.element.find("#pluginRenameForm").get(0).remove();
                this.createPluginRenameForm(data);
            }
            if (angular.isDefined(this.extraData.access)) {
                $localStorage.noteAccess = this.extraData.access;
            }
        }, (response) => {
            $window.alert("Failed to save: " + response.data.error);
        });
        if (this.options.touchDevice) {
            this.changeMeta();
        }
    }

    /**
     * Function that creates a form for renaming plugins with duplicate tasknames
     * @param data - The data received after saving editor text
     */
    createPluginRenameForm(data: { duplicates: Duplicate[] }) {
        // Hides other texteditor elements when form is created
        this.renameFormShowing = true;
        this.duplicates = data.duplicates;
        // Get the editor div
        const editor = this.element;
        // Create a new div
        let $actionDiv = $("<div>", {class: "pluginRenameForm", id: "pluginRenameForm"});
        $actionDiv.css("position", "relative");
        // Add warning and info texts
        $actionDiv.append($("<strong>", {
            text: "Warning!",
        }));
        $actionDiv.append($("<p>", {
            text: "There are multiple objects with the same task name in this document.",
        }));
        $actionDiv.append($("<p>", {
            text: "Plugins with duplicate task names might not work properly.",
        }));
        $actionDiv.append($("<p>", {
            text: 'Rename the duplicates by writing new names in the field(s) below and click "Save",',
        }));
        $actionDiv.append($("<p>", {
            text: 'choose "Rename automatically" or "Ignore" to proceed without renaming.',
        }));
        $actionDiv.append($("<strong>", {
            text: "Rename duplicates:",
        }));

        // Create the rename form
        const $form = $("<form>");
        this.inputs = [];
        let input;
        let span;

        // Add inputs and texts for each duplicate
        for (let i = 0; i < data.duplicates.length; i++) {
            // Make a span element
            span = $("<span>");
            span.css("display", "block");
            // Add a warning if the plugin has answers related to it
            const $warningSpan = $("<span>", {
                class: "pluginRenameExclamation",
                text: "!",
                title: "There are answers related to this task. Those answers might be lost upon renaming this task.",
            });
            if (data.duplicates[i][2] !== "hasAnswers") {
                $warningSpan.css("visibility", "hidden");
            }
            span.append($warningSpan);
            // Add the duplicate name
            span.append($("<label>", {
                class: "pluginRenameObject",
                text: data.duplicates[i][0],
                for: "newName" + i,
            }));
            // Add input field for a new name to the duplicate
            input = $("<input>", {
                class: "pluginRenameObject",
                type: "text",
                id: data.duplicates[i][1],
            });
            // Add the span to the form
            this.inputs.push(input);
            span.append(input);
            $form.append(span);
        }
        // Make a new div for buttons
        const $buttonDiv = $("<div>");
        // A button for saving with input field values or automatically if no values given
        $buttonDiv.append($("<button>", {
            "class": "timButton, pluginRenameObject",
            "text": "Save",
            "title": "Rename task names with given names (Ctrl + S)",
            "ng-click": "$ctrl.renameTaskNamesClicked(inputs, duplicates, true)",
        }));
        // Button for renaming duplicates automatically
        $buttonDiv.append($("<button>", {
            "class": "timButton, pluginRenameObject",
            "text": "Rename Automatically",
            "title": "Rename duplicate task names automatically",
            "ng-click": "$ctrl.renameTaskNamesClicked(undefined, duplicates, true)",
        }));
        // Button for ignoring duplicates
        $buttonDiv.append($("<button>", {
            "class": "timButton, pluginRenameObject",
            "text": "Ignore",
            "title": "Proceed without renaming",
            "ng-click": "$ctrl.renameTaskNamesClicked(undefined, undefined, false)",
        }));
        // Button that allows user to return to edit and cancel save
        $buttonDiv.append($("<button>", {
            "class": "timButton, pluginRenameObject",
            "text": "Cancel",
            "title": "Return to editor",
            "ng-click": "$ctrl.cancelPluginRenameClicked()",
        }));
        // Add the new divs to editor container
        $actionDiv.append($form);
        $actionDiv.append($buttonDiv);
        $actionDiv = $compile($actionDiv)(this.scope);
        editor.append($actionDiv);
        // Focus the first input element
        this.inputs[0].focus();
        this.pluginRenameForm = $actionDiv;
        // Add hotkey for quick saving (Ctrl + S)
        this.pluginRenameForm.keydown((e: KeyboardEvent) => {
            if (e.ctrlKey) {
                if (e.keyCode === 83) {
                    this.renameTaskNamesClicked(this.inputs, this.duplicates, true);
                    e.preventDefault();
                }
            }
        });
    }

    saveClicked() {
        if (this.saving) {
            return;
        }
        this.saving = true;
        // if ( $scope.wrap.n != -1) //  wrap -1 is not saved
        this.setLocalValue("wrap", "" + this.wrap.n);
        if (this.renameFormShowing) {
            this.renameTaskNamesClicked(this.inputs, this.duplicates, true);
        }
        if (this.previewReleased) {
            this.savePreviewData(true);
        } else {
            this.savePreviewData(false);
        }
        const text = this.editor.getEditorText();
        if (text.trim() === "") {
            this.deleteClicked();
            this.saving = false;
            return;
        }
        $http.post<{
            duplicates: Duplicate[],
            original_par: string,
            new_par_ids: string[],
        }>(this.saveUrl, angular.extend({
            text,
        }, this.extraData)).then((response) => {
            const data = response.data;
            if (data.duplicates.length > 0) {
                this.data = data;
                this.createPluginRenameForm(data);
                if (data.original_par != null) {
                    this.originalPar = data.original_par;
                }
                if (data.new_par_ids != null) {
                    this.newPars = data.new_par_ids;
                }
            }
            if (data.duplicates.length <= 0) {
                if (this.options.destroyAfterSave) {
                    this.destroy();
                }
                this.afterSave({
                    extraData: this.extraData,
                    saveData: data,
                });
            }
            if (angular.isDefined(this.extraData.access)) {
                $localStorage.noteAccess = this.extraData.access;
            }
            if (angular.isDefined(this.extraData.tags.markread)) { // TODO: tee silmukassa
                $window.localStorage.setItem("markread", this.extraData.tags.markread.toString());
            }
            this.setLocalValue("proeditor", this.proeditor.toString());

            if (this.isAce(this.editor)) {
                this.setLocalValue("acewrap", this.editor.editor.getSession().getUseWrapMode().toString());
                this.setLocalValue("acebehaviours", this.editor.editor.getBehavioursEnabled().toString()); // some of these are in editor and some in session?
            }
            this.saving = false;

        }, (response) => {
            $window.alert("Failed to save: " + response.data.error);
            this.saving = false;
        });
        if (this.options.touchDevice) {
            this.changeMeta();
        }
    }

    aceEnabled(): boolean {
        return this.isAce(this.editor);
    }

    isAce(editor: AceParEditor | TextAreaParEditor): editor is AceParEditor {
        return editor && (editor.editor as IAceEditor).renderer != null;
    }

    saveOldMode(oldMode: string) {
        this.setLocalValue("oldMode", oldMode);
    }

    onFileSelect(file: File) {
        this.uploadedFile = "";
        this.editor.focus();
        this.file = file;
        const editorText = this.editor.getEditorText();
        let autostamp = false;
        let attachmentParams = undefined;

        // to identify attachment-macro
        let macroStringBegin = "%%liite(";
        let macroStringEnd = ")%%";

        // if there's an attachment macro in editor, assume need to stamp
        // also requires data from preamble to work correctly (dates and knro)
        // if there's no stampFormat set in preamble, uses hard coded default format
        if (editorText.length > 0 && editorText.lastIndexOf(macroStringBegin) > 0) {
            autostamp = true;
            const macroParams = editorText.substring(
                editorText.lastIndexOf(macroStringBegin) + macroStringBegin.length,
                editorText.lastIndexOf(macroStringEnd)).split(",");
            const knro = this.docSettings.macros.knro;
            const dates = this.docSettings.macros.dates;
            const kokousDate = dates[knro];
            const stampFormat = this.docSettings.macros.stampformat;
            attachmentParams = [kokousDate, stampFormat, ...macroParams, autostamp];
        }
        if (file) {
            this.file.progress = 0;
            this.file.error = undefined;
            const upload = $upload.upload<{ image: string, file: string }>({
                data: {
                    file,
                    attachmentParams: JSON.stringify(attachmentParams),
                },
                method: "POST",
                url: "/upload/",
            });

            // TODO: better check for cases with multiple paragraphs
            upload.then((response) => {
                $timeout(() => {
                    var isplugin = (this.editor.editorStartsWith("``` {"));
                    var start = "[File](";
                    if (response.data.image) {
                        this.uploadedFile = "/images/" + response.data.image;
                        start = "![Image](";
                    } else {
                        this.uploadedFile = "/files/" + response.data.file;
                    }
                    if (isplugin) {
                        this.editor.insertTemplate(this.uploadedFile);
                    } else {
                        this.editor.insertTemplate(start + this.uploadedFile + ")");
                    }
                });
            }, (response) => {
                if (response.status > 0) {
                    this.file.error = response.data.error;
                }
            }, (evt) => {
                this.file.progress = Math.min(100, Math.floor(100.0 *
                    evt.loaded / evt.total));
            });

            upload.finally(() => {
            });
        }
    }

    closeMenu(e: JQueryEventObject | null, force: boolean) {
        const container = $(MENU_BUTTON_CLASS_DOT);
        if (force || (e != null && !container.is(e.target) && container.has(e.target as Element).length === 0)) {
            container.remove();
            $(document).off("mouseup.closemenu");
        }
    }

    createMenuButton(text: string, title: string, clickfunction: string) {
        const $span = $("<span>", {class: "actionButtonRow"});
        const button_width = 130;
        $span.append($("<button>", {
            "class": "timButton editMenuButton",
            "text": text,
            "title": title,
            "ng-click": clickfunction + "; $ctrl.closeMenu($event, true); $ctrl.wrapFn()",
            // "width": button_width,
        }));
        return $span;
    }

    createMenu($event: Event, buttons: JQuery[]) {
        this.closeMenu(null, true);
        const $button = $($event.target);
        const coords = {left: $button.position().left, top: $button.position().top};
        let $actionDiv = $("<div>", {class: MENU_BUTTON_CLASS});

        for (let i = 0; i < buttons.length; i++) {
            $actionDiv.append(buttons[i]);
        }

        $actionDiv.append(this.createMenuButton("Close menu", "", ""));
        $actionDiv.offset(coords);
        $actionDiv.css("position", "absolute"); // IE needs this
        $actionDiv = $compile($actionDiv)(this.scope);
        $button.parent().prepend($actionDiv);
        $(document).on("mouseup.closemenu", (e: JQueryEventObject) => this.closeMenu(e, false));
    }

    tableClicked($event: Event) {
        const buttons = [];
        for (const key in this.tables) {
            if (this.tables.hasOwnProperty(key)) {
                const text = key.charAt(0).toUpperCase() + key.substring(1);
                const clickfn = "$ctrl.editor.insertTemplate($ctrl.tables['" + key + "'])";
                buttons.push(this.createMenuButton(text, "", clickfn));
            }
        }
        this.createMenu($event, buttons);
    }

    slideClicked($event: Event) {
        const buttons = [];
        buttons.push(this.createMenuButton("Slide break", "Break text to start a new slide", "$ctrl.editor.ruleClicked()"));
        buttons.push(this.createMenuButton("Slide fragment", "Content inside the fragment will be hidden and shown when next is clicked in slide view", "$ctrl.editor.surroundClicked('§§', '§§')"));
        buttons.push(this.createMenuButton("Fragment block", "Content inside will show as a fragment and may contain inner slide fragments", "$ctrl.editor.surroundClicked('<§', '§>')"));
        this.createMenu($event, buttons);
    }

    pluginClicked($event: Event, key: string) {
        this.createMenu($event, this.pluginButtonList[key]);
    }

    putTemplate(data: string) {
        if (!this.touchDevice) {
            this.editor.focus();
        }
        this.editor.insertTemplate(data);
    }

    getTemplate(plugin: string, template: string, index: string) {
        $.ajax({
            type: "GET",
            url: "/" + plugin + "/template/" + template + "/" + index,
            dataType: "text",
            processData: false,
            success: (data) => {
                data = data.replace(/\\/g, "\\\\");
                this.editor.insertTemplate(data);
            },
            error() {
                $log.error("Error getting template");
            },
        });
        if (!this.touchDevice) {
            this.editor.focus();
        }
    }

    tabClicked($event: Event, area: string) {
        const active = $($event.target).parent();
        setSetting("editortab", area);
        this.setActiveTab(active, area);
        this.wrapFn();
    }

    /**
     * Sets active tab
     * @param active tab <li> element
     * @param area area to make visible
     */
    setActiveTab(active: JQuery, area: string) {
        const naviArea = this.element.find("#" + area);
        const buttons = this.element.find(".extraButtonArea");
        const tabs = this.element.find(".tab");
        for (let i = 0; i < buttons.length; i++) {
            $(buttons[i]).attr("class", "extraButtonArea hidden");
        }
        for (let j = 0; j < tabs.length; j++) {
            $(tabs[j]).removeClass("active");
        }
        $(active).attr("class", "tab active");
        $(naviArea).attr("class", "extraButtonArea");
    }

    /**
     * @returns {boolean} true if device supports fullscreen, otherwise false
     */
    fullscreenSupported() {
        const div: any = $(this.element).get(0);
        const requestMethod = div.requestFullScreen ||
            div.webkitRequestFullscreen ||
            div.webkitRequestFullScreen ||
            div.mozRequestFullScreen ||
            div.msRequestFullscreen;
        return (typeof (requestMethod) !== "undefined");
    }

    /**
     * Makes editor div fullscreen
     */
    goFullScreen() {
        const div: any = $(this.element).find("#pareditor").get(0);
        const doc: any = document;
        if (!doc.fullscreenElement &&    // alternative standard method
            !doc.mozFullScreenElement && !doc.webkitFullscreenElement && !doc.msFullscreenElement) {

            const requestMethod = div.requestFullScreen ||
                div.webkitRequestFullscreen ||
                div.webkitRequestFullScreen ||
                div.mozRequestFullScreen ||
                div.msRequestFullscreen;

            if (requestMethod) {
                requestMethod.apply(div);
                div.setAttribute("style", "width: 100%; height: 100%; position: absolute; top: 0px;" +
                    "padding: 2em 5px 5px 5px; background: rgb(224, 224, 224); -webkit-box-sizing: border-box;" +
                    "-moz-box-sizing: border-box; box-sizing: border-box;");
            }
        } else {
            if (doc.exitFullscreen) {
                doc.exitFullscreen();
            } else if (doc.msExitFullscreen) {
                doc.msExitFullscreen();
            } else if (doc.mozCancelFullScreen) {
                doc.mozCancelFullScreen();
            } else if (doc.webkitExitFullscreen) {
                doc.webkitExitFullscreen();
            }
        }
    }

    /**
     * Switches editor between Ace and textarea.
     */
    async changeEditor(newMode: string) {
        let text = "";
        const editorContainer = this.element.find(".editorContainer");
        editorContainer.addClass("editor-loading");
        if (this.editor) {
            text = this.editor.getEditorText();
        }
        let oldeditor = null;
        if (this.isAce(this.editor) || newMode === "text") {
            oldeditor = this.element.find("#ace_editor");
            oldeditor.remove();
            this.saveOldMode("text");
            this.createTextArea(text);
        } else {
            oldeditor = this.element.find("#teksti");
            oldeditor.remove();
            const ace = (await import("tim/ace")).ace;
            this.saveOldMode("ace");
            const neweditorElem = $("<div>", {
                class: "editor",
                id: "ace_editor",
            });
            editorContainer.append(neweditorElem);
            const neweditor = ace.edit(neweditorElem[0]);

            this.editor = new AceParEditor(ace, neweditor, {
                wrapFn: () => this.wrapFn(),
                saveClicked: () => this.saveClicked(),
                getWrapValue: () => this.wrap.n,
            }, (this.lstag === "addAbove" || this.lstag === "addBelow") ? "ace/mode/text" : "ace/mode/markdown");
            if (!this.minSizeSet) {
                this.setEditorMinSize();
            }
            this.editor.setAutoCompletion(this.autocomplete);
            this.editor.editor.renderer.$cursorLayer.setBlinking(!$window.IS_TESTING);
            /*iPad does not open the keyboard if not manually focused to editable area
             var iOS = /(iPad|iPhone|iPod)/g.test($window.navigator.platform);
             if (!iOS) editor.focus();*/

            neweditor.getSession().on("change", () => {
                this.editorChanged();
            });
            neweditor.setBehavioursEnabled(this.getLocalBool("acebehaviours", false));
            neweditor.getSession().setUseWrapMode(this.getLocalBool("acewrap", false));
            neweditor.setOptions({maxLines: 28});
            this.editor.setEditorText(text);

            const langTools = ace.require("ace/ext/language_tools");

            const wordListStr = (await $http.get<{ word_list: string }>("/settings/get/word_list", {params: {_: Date.now()}})).data.word_list;
            const userWordList = wordListStr ? wordListStr.split("\n") : [];
            const createCompleter = (wordList: string[], context: string) => ({
                getCompletions(editor: any, session: any, pos: any, prefix: any, callback: any) {
                    callback(null, wordList.map((word) => ({
                        caption: word,
                        meta: context,
                        value: word,
                    })));
                },
            });
            langTools.setCompleters([
                langTools.snippetCompleter,
                langTools.textCompleter,
                langTools.keyWordCompleter,
                createCompleter($window.wordList, "document"),
                createCompleter(userWordList, "user"),
            ]);
        }
        try {
            await this.setInitialText();
        } catch (response) {
            if (response.status === 404) {
                if (this.extraData.isComment) {
                    $window.alert("This comment has been deleted.");
                } else {
                    $window.alert("This paragraph has been deleted.");
                }
            } else {
                $window.alert("Error occurred: " + response.data.error);
            }
            $timeout(() => {
                this.destroy();
            }, 1000);
            return;
        }
        this.editorReady();
        setEditorScope(this.editor);
        this.adjustPreview();
        if (!this.proeditor && this.lstag === "note") {
            const editor = this.element;
            editor.css("max-width", "40em");
        }
    }
}

timApp.component("pareditor", {
    templateUrl: "/static/templates/parEditor.html",
    bindings: {
        saveUrl: "@",
        deleteUrl: "@",
        previewUrl: "@",
        unreadUrl: "@",
        extraData: "=",
        afterSave: "&",
        afterCancel: "&",
        afterDelete: "&",
        options: "=",
        initialTextUrl: "@",
    },
    require: {
        draggable: "?^timDraggableFixed",
    },
    controller: PareditorController,
});
