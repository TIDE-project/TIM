/**
 * Defines the client-side implementation of a dropdown plugin.
 */
import angular from "angular";
import * as t from "io-ts";
import {ITimComponent, ViewCtrl} from "tim/document/viewctrl";
import {GenericPluginMarkup, Info, PluginBase, withDefault} from "tim/plugin/util";
import {to} from "tim/util/utils";
import {$http} from "tim/util/ngimport";

const dropdownApp = angular.module("dropdownApp", ["ngSanitize"]);
export const moduleDefs = [dropdownApp];

const DropdownMarkup = t.intersection([
    t.partial({
        words: t.array(t.string),
    }),
    GenericPluginMarkup,
    t.type({
        // all withDefaults should come here; NOT in t.partial,
        instruction: withDefault(t.boolean, false),
        radio: withDefault(t.boolean, false),
    }),
]);
const DropdownAll = t.intersection([
    t.partial({
        userword: t.string,
    }),
    t.type({
        info: Info,
        markup: DropdownMarkup,
        preview: t.boolean,
    }),
]);

class DropdownController extends PluginBase<t.TypeOf<typeof DropdownMarkup>, t.TypeOf<typeof DropdownAll>, typeof DropdownAll> implements ITimComponent {
    private error?: string;
    private wordList?: string[];
    private selectedWord?: string;
    private vctrl!: ViewCtrl;

    getDefaultMarkup() {
        return {};
    }

    $onInit() {
        super.$onInit();
        this.wordList = this.attrs.words || [];
        this.addToCtrl();
    }

    /**
     * Adds this plugin to ViewCtrl so other plugins can get information about the plugin though it.
     */
    addToCtrl() {
        this.vctrl.addTimComponent(this);
    }

    /**
     * Returns the selected choice from the dropdown-list.
     * @returns {string} The selected choice..
     */
    getContent(): string {
        return this.selectedWord || "";
    }

    /**
     * TODO: whole sentence, selected option, plugin type?,
     */
    async save() {
        const failure = await this.doSave(this.attrs.instruction);
        return failure;
    }

    async doSave(nosave: boolean) {
        const params = {
            input: {
                nosave: false,
                selectedWord: this.selectedWord,
                id: Date.now(),
            },
        };

        if (nosave) {
            params.input.nosave = true;
        }

        const url = this.pluginMeta.getAnswerUrl();
        const r = await to($http.put<{ web: { result: string, error?: string } }>(url, params));

        if (r.ok) {
            const data = r.result.data;
            this.error = data.web.error;
            if (data.web.error) {
                return data.web.error;
            }
            // this.result = data.web.result;
        } else {
            this.error = "Infinite loop or some other error?";
        }
    }

    /**
     * Sets the words visible in the plugin and randomizes their order
     *
     * @param words List of words to be shown in the plugin
     */
    setPluginWords(words: string[]) {
        // shuffle algorithm from csparsons.ts
        const result = words.slice();
        const n = words.length;
        for (let i = n - 1; i >= 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            const tmp = result[i];
            result[i] = result[j];
            result[j] = tmp;
        }

        this.wordList = result;
        this.selectedWord = "";
    }

    protected getAttributeType() {
        return DropdownAll;
    }
}

dropdownApp.component("dropdownRunner", {
    bindings: {
        json: "@",
    },
    controller: DropdownController,
    require: {
        vctrl: "^timView",
    },
    template: `
<div>
    <tim-markup-error ng-if="::$ctrl.markupError && !$ctrl.teacherRight" data="::$ctrl.markupError"></tim-markup-error>
    <h4 ng-if="::$ctrl.header" ng-bind-html="::$ctrl.header"></h4>
    <p ng-if="::$ctrl.stem">{{::$ctrl.stem}}</p>
    <div class="form-inline"><label><span>
        <select ng-model="$ctrl.selectedWord" ng-options="item for item in $ctrl.wordList">
        </select>
        </span></label>
    </div>
    <div ng-if="$ctrl.error" ng-bind-html="$ctrl.error"></div>
    <p ng-if="::$ctrl.footer" ng-bind="::$ctrl.footer" class="plgfooter"></p>
</div>
`,
});


// <span ng-if="$ctrl.radio" ng-repeat="item in $ctrl.words">
//         <input type="radio" name="radio" ng-value="item" ng-model="$ctrl.selectedWord">{{item}}
//         </span>