import {Component, NgModule, OnInit} from "@angular/core";
import {CommonModule} from "@angular/common";

// import {TimMessage} from "tim/timApp/messaging/timMessage/timMessage";

@Component({
    selector: "tim-message",
    template: `
        <ng-container *ngIf="showMessage">
            <div class="timMessageDisplay">
                <p>From: {{sender}}</p>
                <p class="message-heading">{{heading}}</p>
                <div class="fullMessageContent" *ngIf="showFullContent">
                    <p>{{fullContent}}</p>
                    <p *ngIf="messageOverMaxLength"><a (click)="toggleDisplayedContentLength()">Read less</a></p>
                </div>
                <div class="cutMessageContent" *ngIf="!showFullContent">
                    <p>{{shownContent}}<span>...</span></p>
                    <p><a (click)="toggleDisplayedContentLength()">Read more</a></p>
                </div>
                <div class="buttonArea">
                    <button class="timButton" *ngIf="canReply" (click)="reply()">Reply</button>
                    <span><a (click)="readReceipt()">TEST: allow/disallow read receipt</a></span>
                </div>
                <div class="replyArea" *ngIf="showReply">
                    <p>To: {{sender}}</p>
                    <textarea id="reply-message" name="reply-message"></textarea>
                    <div class="sent">
                        <button class="timButton" [disabled]="!canSendReply" (click)="sendReply()">Send</button>
                        <span *ngIf="replySent">Sent!</span>
                    </div>
                </div>
                <div class="readReceiptArea">
                    <input type="checkbox" name="mark-as-read" id="mark-as-read" [disabled]="!canMarkAsRead"
                           (click)="markAsRead()"/>
                    <label for="mark-as-read">Mark as Read</label>
                    <span class="readReceiptLink"
                          *ngIf="markedAsRead">Read receipt can be cancelled in <a>your messages</a></span>
                    <button class="timButton" title="Close Message" [disabled]="!markedAsRead" (click)="closeMessage()">
                        Close
                    </button>
                </div>
            </div>
        </ng-container>
    `,
    styleUrls: ["tim-message.component.scss"],
})
export class TimMessageComponent implements OnInit {
    messageMaxLength: number = 210;
    messageOverMaxLength: boolean = true;
    showMessage: boolean = true;
    fullContent?: string;
    shownContent?: string;
    showFullContent: boolean = false;
    showReply: boolean = false;
    canMarkAsRead: boolean = true;
    markedAsRead: boolean = false;
    replySent: boolean = false;
    canReply: boolean = true; // show/hide 'Reply' button
    canSendReply: boolean = true; // enable/disable 'Send' button
    sender?: string;
    heading?: string;

    /**
     * Toggles between showing the full message content and the shortened version.
     */
    toggleDisplayedContentLength(): void {
        this.showFullContent = !this.showFullContent;
    }

    /**
     * Hides the message view; shows an alert about sending a read receipt and an option to cancel.
     */
    markAsRead(): void {
        this.markedAsRead = !this.markedAsRead;
    }

    /**
     * Shows or hides the reply area.
     */
    reply(): void {
        this.showReply = !this.showReply;
    }

    /**
     * Allows/disallows marking as read for testing purposes.
     */
    readReceipt(): void {
        this.canMarkAsRead = !this.canMarkAsRead;
    }

    /**
     * Shows a "sent" alert after sending a reply.
     */
    sendReply(): void {
        this.replySent = true;
        this.canSendReply = false;
    }

    /**
     * Hides the entire message.
     */
    closeMessage(): void {
        this.showMessage = false;
    }

    ngOnInit(): void {
        // TODO Read sender, content etc. from database
        this.sender = "Matti Meikäläinen";
        this.heading = "Puuttuvat demopisteet";
        // this.fullContent =
        //     "Sinulta puuttuu demo 3 ja 4 pisteitä. Miten jatketaan kurssin kanssa?";
        this.fullContent =
            "Sinulta puuttuu demo 3 ja 4 pisteitä. Miten jatketaan kurssin kanssa? \
            Kullakin demokerralla 100% oikeuttava määrä on 8 pistettä. Kultakin \
            demokerralta lasketaan jakson 1 aikana max. 10 p, eli vaikka saisit \
            kerättyä lisätehtävillä enemmänkin pisteitä, otetaan jokaiselta demokerralta \
            lukuun enintään 10 pistettä. Jakso 2 max 8p/kerta. Muutos: paitsi demo 12 \
            jolloin määrällä ei ole ylärajaa. HUOM! 2 tehtävää / kerta ei kuitenkaan \
            riitä kurssin läpäisemiseen, sillä ensinnäkään siitä ei tule yhteensä 40% \
            ja toisekseen joka kerta jää 6 tehtävää muita jälkeen. 12 kerran jälkeen on \
            melkoisen paljon muita jäljessä! 105 % suoritustavassa on JOKA demokerta \
            tehtävä vähintään yksi Bonus- tai Guru-tehtävä (vuonna 2018 ekassa jaksossa, \
            jatkossa molemmissa jaksoissa).";
        if (this.fullContent.length < this.messageMaxLength) {
            this.messageOverMaxLength = false;
            this.showFullContent = true;
        } else {
            this.shownContent = this.fullContent.substr(
                0,
                this.messageMaxLength
            );
        }
    }
}

@NgModule({
    declarations: [TimMessageComponent],
    exports: [TimMessageComponent],
    imports: [CommonModule],
})
export class TimMessageModule {}
