/* eslint no-underscore-dangle: ["error", { "allow": ["_visible"] }] */
/**
 * Formula Editor for inputting LaTeX math
 * @author Juha Reinikainen
 * @licence MIT
 * @date 28.2.2023
 */

import type {OnInit} from "@angular/core";
import {
    Component,
    ElementRef,
    EventEmitter,
    Input,
    Output,
    ViewChild,
} from "@angular/core";
import {FormControl} from "@angular/forms";
import type {
    IMathQuill,
    MathFieldMethods,
    MathQuillConfig,
} from "vendor/mathquill/mathquill";
import {IEditor} from "../editor";

/**
 * Field which has the focus
 */
enum ActiveEditorType {
    Visual = "visual",
    Latex = "latex",
}

export type FormulaResult = {
    latex: string;
    isMultiline: boolean;
};

@Component({
    selector: "cs-formula-editor",
    template: `
        <dialog #formulaDialog class="formula-editor-dialog">
            <div class="formula-container">
                <span class="visual-input" #visualInput></span>
    
                <textarea name="math-editor-output" #latexInput cols="30" rows="5"
                          (click)="handleLatexFocus()"
                          (keyup)="handleLatexInput()"
                          [formControl]="latexInputControl"
                          placeholder="write LaTeX">
                </textarea>                    
            </div>
    
            <div class="formula-button-container">
                <div class="formula-buttons">
                    <button class="timButton" (click)="handleFormulaOk()">Ok</button>
                    <button class="timButton" (click)="handleFormulaCancel()">Cancel</button>                                        
                </div>
    
                <label class="font-weight-normal">
                    <input type="checkbox" [formControl]="isMultilineFormulaControl">
                    Multiline
                </label>
            </div>
        </dialog>
    `,
    styleUrls: ["./formula-editor.component.scss"],
})
export class FormulaEditorComponent implements OnInit, IEditor {
    latexInputControl = new FormControl("");
    @ViewChild("latexInput") latexInput!: ElementRef<HTMLTextAreaElement>;

    @ViewChild("visualInput") visualInput!: ElementRef<HTMLElement>;
    MQ!: IMathQuill;

    mathField!: MathFieldMethods;

    activeEditor: ActiveEditorType = ActiveEditorType.Visual;

    content: string = "";

    @Output() okEvent = new EventEmitter<void>();
    @Output() cancelEvent = new EventEmitter<void>();

    isMultilineFormulaControl = new FormControl(true);

    @ViewChild("formulaDialog") formulaDialog!: ElementRef<HTMLDialogElement>;

    @Input()
    get visible(): boolean {
        return this._visible;
    }
    set visible(isVis: boolean) {
        this._visible = isVis;
        if (this.formulaDialog && isVis) {
            this.content = this.editor?.content ?? this.content;
            this.formulaDialog.nativeElement.show();
        } else if (this.formulaDialog) {
            this.formulaDialog.nativeElement.close();
        }
    }
    private _visible: boolean = false;

    @Input() editor?: IEditor;

    constructor() {}

    ngOnInit(): void {
        this.latexInputControl.valueChanges.subscribe((value) => {
            this.updateFormulaToEditor();
        });
    }

    focus(): void {}

    editHandler(field: MathFieldMethods) {
        // write changes in visual field to latex field if visual field
        // was the one modified
        if (this.activeEditor === ActiveEditorType.Visual) {
            const latex = field.latex();
            this.latexInputControl.setValue(latex);
        }
    }

    enterHandler(field: MathFieldMethods) {
        this.handleFormulaOk();
    }

    async loadMathQuill() {
        const elem = this.visualInput.nativeElement;
        elem.addEventListener("click", (_e: MouseEvent) => {
            this.activeEditor = ActiveEditorType.Visual;
        });
        const config: MathQuillConfig = {
            spaceBehavesLikeTab: true,
            handlers: {
                edit: (field: MathFieldMethods) => this.editHandler(field),
                enter: (field: MathFieldMethods) => this.enterHandler(field),
            },
        };
        const mq = (await import("vendor/mathquill/mathquill")).default;
        this.MQ = mq.getInterface(2);

        this.mathField = this.MQ.MathField(elem, config);
    }

    ngAfterViewInit() {
        void this.loadMathQuill();
    }

    handleLatexFocus() {
        this.activeEditor = ActiveEditorType.Latex;
    }

    handleLatexInput() {
        // write changes in latex field to visual field if latex field
        // was the one modified
        if (
            this.activeEditor === ActiveEditorType.Latex &&
            this.latexInputControl.value !== null
        ) {
            this.mathField.latex(this.latexInputControl.value);
        }
    }

    clearFields() {
        this.mathField.latex("");
        this.latexInputControl.setValue("");
    }

    formatLatex(latex: string, isMultiline: boolean): string {
        const wrapSymbol = isMultiline ? "$$" : "$";
        if (isMultiline) {
            const multilineLatex = latex.split("\n").join("\\\\\n");
            return `${wrapSymbol}\n${multilineLatex}\\\\\n${wrapSymbol}\n`;
        }
        return `${wrapSymbol}${latex}${wrapSymbol}`;
    }

    updateFormulaToEditor() {
        if (
            this.latexInputControl.value &&
            this.isMultilineFormulaControl.value !== null
        ) {
            const isMultiline = this.isMultilineFormulaControl.value;
            const latex = isMultiline
                ? this.latexInputControl.value
                : this.mathField.latex();
            if (typeof latex === "string") {
                const formulaLatex = this.formatLatex(latex, isMultiline);
                if (this.editor) {
                    this.editor.content = this.content + formulaLatex;
                }
            }
        }
    }

    handleFormulaOk() {
        this.updateFormulaToEditor();
        this.okEvent.emit();
        this.clearFields();
    }

    handleFormulaCancel() {
        if (this.editor) {
            this.editor.content = this.content;
        }
        this.cancelEvent.emit();
        this.clearFields();
    }

    setReadOnly(b: boolean): void {}
}
