/**
 * Utility functions for formula editor
 *
 * @author Juha Reinikainen
 * @licence MIT
 * @data 4.4.2023
 */

import type {IEditor} from "../editor";

/**
 * Preview formula is inside parent .math class element
 * and contains latex as a string.
 */
type PreviewFormula = {
    latex: string;
    element: Element;
};

/**
 * Gets latex from preview.
 * @param event
 * @param previewRoot preview root element
 */
function getLatexFromPreview(
    event: MouseEvent,
    previewRoot: Element
): PreviewFormula | undefined {
    // try to find root of formula
    let current = event.target;
    if (!current || !(current instanceof Element)) {
        return undefined;
    }

    // traverse parents until element with math class is found
    // or until previewRoot which indicates we probably weren't inside any formula
    while (current !== previewRoot && current instanceof Element) {
        if (current.classList.contains("math")) {
            const annotation = current.querySelector("annotation");
            if (!annotation || !annotation.textContent) {
                return undefined;
            }
            const latex = annotation.textContent.trim();
            return {latex: latex, element: current};
        }
        current = current.parentElement;
    }
    return undefined;
}

/**
 * Moves past formulas before this and returns where
 * to start looking for clicked formula.
 * @param clicked clicked formula in preview
 * @param editor editor containing formulas
 * @param previewRoot preview root element
 * @return index in editor.content or -1 if couldn't find
 */
function movePastFormulasBeforeClicked(
    clicked: PreviewFormula,
    editor: IEditor,
    previewRoot: Element
): number {
    let index = 0;
    const content = editor.content.replace(/\n/g, " ");

    for (const mathElem of previewRoot.querySelectorAll(".math")) {
        // stop when clicked element is reached
        if (mathElem === clicked.element) {
            return index;
        }
        const annotation = mathElem.querySelector("annotation");
        // probably shouldn't happen
        if (!annotation || !annotation.textContent) {
            continue;
        }
        const latex = annotation.textContent.trim().replace(/\n/g, " ");
        const nextIndex = content.indexOf(latex, index);
        if (nextIndex === -1) {
            return -1;
        }
        index = nextIndex + latex.length;
    }
    return index;
}

/**
 * Moves cursor inside clicked formula in preview in editor.
 * @param event mouse click event
 * @param editor editor containing latex that was rendered to preview
 * @param previewRoot preview root element
 * @return whether the formula was found and cursor was moved to it
 */
export function selectFormulaFromPreview(
    event: MouseEvent,
    editor: IEditor,
    previewRoot: Element
) {
    const clickedPreviewFormula = getLatexFromPreview(event, previewRoot);
    if (!clickedPreviewFormula) {
        return false;
    }
    const startI = movePastFormulasBeforeClicked(
        clickedPreviewFormula,
        editor,
        previewRoot
    );
    if (startI === -1) {
        return false;
    }
    const i = editor.content
        .replace(/\n/g, " ")
        .indexOf(clickedPreviewFormula.latex.replace(/\n/g, " "), startI);
    if (i === -1) {
        return false;
    }
    if (!editor.moveCursorToContentIndex) {
        return false;
    }
    editor.moveCursorToContentIndex(i);
    return true;
}
