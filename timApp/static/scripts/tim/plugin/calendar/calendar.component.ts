import {
    ApplicationRef,
    ChangeDetectionStrategy,
    ChangeDetectorRef,
    // ChangeDetectorRef,
    Component,
    DoBootstrap,
    ElementRef,
    // Injectable,
    NgModule,
    OnInit,
    ViewEncapsulation,
} from "@angular/core";
import {BrowserAnimationsModule} from "@angular/platform-browser/animations";
import * as t from "io-ts";
import {
    CalendarDateFormatter,
    CalendarEvent,
    // CalendarEventTitleFormatter,
    CalendarModule,
    CalendarView,
    DateAdapter,
} from "angular-calendar";
import {WeekViewHourSegment} from "calendar-utils";
import {adapterFactory} from "angular-calendar/date-adapters/date-fns";
import {platformBrowserDynamic} from "@angular/platform-browser-dynamic";
import {CommonModule, registerLocaleData} from "@angular/common";
import localeFr from "@angular/common/locales/fi";
import {HttpClient, HttpClientModule} from "@angular/common/http";
import {FormsModule} from "@angular/forms";
import {BrowserModule, DomSanitizer} from "@angular/platform-browser";
import {finalize, fromEvent, takeUntil} from "rxjs";
import {addDays, addMinutes, endOfWeek} from "date-fns";
import moment from "moment";
import {createDowngradedModule, doDowngrade} from "../../downgrade";
import {AngularPluginBase} from "../angular-plugin-base.directive";
import {GenericPluginMarkup, getTopLevelFields, nullable} from "../attributes";
import {toPromise} from "../../util/utils";
import {Users} from "../../user/userService";
import {CalendarHeaderModule} from "./calendar-header.component";
import {CustomDateFormatter} from "./custom-date-formatter.service";

/**
 * Helps calculate the size of a horizontally dragged event on the calendar view.
 *
 * @param amount movement of mouse in pixels
 * @param segmentWidth the width of a single day in week view
 */
function floorToNearest(amount: number, segmentWidth: number) {
    return Math.floor(amount / segmentWidth) * segmentWidth;
}

/**
 * Helps calculate the size of a vertically dragged event on the calendar view.
 *
 * @param amount movement of mouse in pixels
 * @param minutesInSegment the length of a single segment in calendar in minutes. An hour is divided into slots in view.
 * @param segmentHeight the height of a single slot in calendar in pixels
 */
function ceilToNearest(
    amount: number,
    minutesInSegment: number,
    segmentHeight: number
) {
    return Math.ceil(amount / segmentHeight) * minutesInSegment;
}

const CalendarItem = t.type({
    done: t.boolean,
    text: t.string,
});

const CalendarMarkup = t.intersection([
    t.partial({
        todos: nullable(t.array(CalendarItem)),
    }),
    GenericPluginMarkup,
]);

const CalendarFields = t.intersection([
    getTopLevelFields(CalendarMarkup),
    t.type({}),
]);

const segmentHeight = 30;
const minutesInSegment = 20;

registerLocaleData(localeFr);

Date.prototype.toJSON = function () {
    return moment(this).format();
};

/**
 * For customizing the event tooltip
 */
/* @Injectable()
export class CustomEventTitleFormatter extends CalendarEventTitleFormatter {
    weekTooltip(event: CalendarEvent<{tmpEvent?: boolean}>, title: string) {
        if (!event.meta?.tmpEvent) {
            return super.weekTooltip(event, title);
        }
        return "";
    }

    dayTooltip(event: CalendarEvent<{tmpEvent?: boolean}>, title: string) {
        if (!event.meta?.tmpEvent) {
            return super.dayTooltip(event, title);
        }
        return "";
    }
}*/

@Component({
    selector: "mwl-calendar-component",
    changeDetection: ChangeDetectionStrategy.OnPush,
    providers: [
        {
            provide: CalendarDateFormatter,
            useClass: CustomDateFormatter,
        },
        // {
        //     provide: CalendarEventTitleFormatter,
        //     useClass: CustomEventTitleFormatter,
        // },
    ],
    template: `
        <mwl-utils-calendar-header [(view)]="view" [(viewDate)]="viewDate">
        </mwl-utils-calendar-header>
        
        <div class="alert alert-info">
          Click on a day or time slot on the view.
          <strong *ngIf="clickedDate"
            >You clicked on this time: {{ clickedDate | date:'medium' }}</strong
          >
          <strong *ngIf="clickedColumn !== undefined"
            >You clicked on this column: {{ clickedColumn }}</strong
          >
        </div>
        
        <ng-template
          #weekViewHourSegmentTemplate
          let-segment="segment"
          let-locale="locale"
          let-segmentHeight="segmentHeight"
          let-isTimeLabel="isTimeLabel"
        >
          <div
            #segmentElement
            class="cal-hour-segment"
            [style.height.px]="segmentHeight"
            [class.cal-hour-start]="segment.isStart"
            [class.cal-after-hour-start]="!segment.isStart"
            [ngClass]="segment.cssClass"
            (mousedown)="startDragToCreate(segment, $event, segmentElement)"
          >
            <div class="cal-time" *ngIf="isTimeLabel">
              {{ segment.date | calendarDate:'weekViewHour':locale }}
            </div>
          </div>
        </ng-template>
        
        <div [ngSwitch]="view">
          <mwl-calendar-month-view
            *ngSwitchCase="'month'"
            [viewDate]="viewDate"
            [events]="events"
            [locale]="'fi-FI'"
            [weekStartsOn]= "1"
            (columnHeaderClicked)="clickedColumn = $event.isoDayNumber"
            (dayClicked)="clickedDate = $event.day.date"
          >
          </mwl-calendar-month-view>
          <mwl-calendar-week-view
            *ngSwitchCase="'week'"
            [viewDate]="viewDate"
            [events]="events"
            [hourSegmentHeight]="30"
            [hourDuration]="60"
            [hourSegments]="3"
            [dayStartHour]="8"
            [dayEndHour]="19"
            [locale]="'fi-FI'"
            [weekStartsOn]= "1"
            (dayHeaderClicked)="clickedDate = $event.day.date"
            (hourSegmentClicked)="clickedDate = $event.date"
            [hourSegmentTemplate]="weekViewHourSegmentTemplate"
          >
          </mwl-calendar-week-view>
          <mwl-calendar-day-view
            *ngSwitchCase="'day'"
            [viewDate]="viewDate"
            [events]="events"
            [hourDuration]="60"
            [hourSegments]="3"
            [dayStartHour]="8" 
            [dayEndHour]="19"
            [locale]="'fi-FI'"
            (hourSegmentClicked)="clickedDate = $event.date"
          >
          </mwl-calendar-day-view>
        </div>
        <div>
            <button class="timButton" id="saveBtn" (click)="saveChanges()" [disabled]="this.events.length === 0">Save changes</button>
        </div>
    `,
    encapsulation: ViewEncapsulation.None,
    styleUrls: ["calendar.component.scss"],
    // templateUrl: "template.html",
})
export class CalendarComponent
    extends AngularPluginBase<
        t.TypeOf<typeof CalendarMarkup>,
        t.TypeOf<typeof CalendarFields>,
        typeof CalendarFields
    >
    implements OnInit
{
    view: CalendarView = CalendarView.Week;

    viewDate: Date = new Date();

    events: CalendarEvent[] = [];

    clickedDate?: Date;

    clickedColumn?: number;

    dragToCreateActive = false;

    weekStartsOn: 1 = 1;

    constructor(
        el: ElementRef<HTMLElement>,
        http: HttpClient,
        domSanitizer: DomSanitizer,
        private cdr: ChangeDetectorRef
    ) {
        super(el, http, domSanitizer);
    }

    startDragToCreate(
        segment: WeekViewHourSegment,
        mouseDownEvent: MouseEvent,
        segmentElement: HTMLElement
    ) {
        const dragToSelectEvent: CalendarEvent<{tmpEvent?: boolean}> = {
            id: this.events.length,
            title: `${segment.date.toTimeString().substr(0, 5)}–${addMinutes(
                segment.date,
                minutesInSegment
            )
                .toTimeString()
                .substr(0, 5)} Varattava aika`,
            start: segment.date,
            end: addMinutes(segment.date, minutesInSegment),
            meta: {
                tmpEvent: true,
            },
        };
        this.events = [...this.events, dragToSelectEvent];
        this.dragToCreateActive = true;
        const segmentPosition = segmentElement.getBoundingClientRect();
        const endOfView = endOfWeek(this.viewDate, {
            weekStartsOn: this.weekStartsOn,
        });

        fromEvent<MouseEvent>(document, "mousemove")
            .pipe(
                finalize(() => {
                    if (dragToSelectEvent.meta) {
                        delete dragToSelectEvent.meta.tmpEvent;
                    }
                    this.dragToCreateActive = false;
                    this.refresh();
                }),
                takeUntil(fromEvent(document, "mouseup"))
            )
            .subscribe((mouseMoveEvent: MouseEvent) => {
                const minutesDiff = ceilToNearest(
                    mouseMoveEvent.clientY - segmentPosition.top,
                    minutesInSegment,
                    segmentHeight
                );
                const daysDiff =
                    floorToNearest(
                        mouseMoveEvent.clientX - segmentPosition.left,
                        segmentPosition.width
                    ) / segmentPosition.width;

                const newEnd = addDays(
                    addMinutes(segment.date, minutesDiff),
                    daysDiff
                );
                if (newEnd > segment.date && newEnd < endOfView) {
                    dragToSelectEvent.end = newEnd;
                    dragToSelectEvent.title = `${segment.date
                        .toTimeString()
                        .substr(0, 5)}–${newEnd
                        .toTimeString()
                        .substr(0, 5)} Varattava aika`;
                }
                this.refresh();
            });
    }

    private refresh() {
        this.events = [...this.events];
        this.cdr.detectChanges();
        console.log(this.events);
    }

    getAttributeType() {
        return CalendarFields;
    }

    getDefaultMarkup() {
        return {};
    }

    ngOnInit() {
        super.ngOnInit();
        if (Users.isLoggedIn()) {
            console.log(Users.getCurrent().name);
            void this.loadEvents();
        }
    }

    private async loadEvents() {
        const result = await toPromise(
            this.http.get<CalendarEvent<{end: Date}>[]>("/calendar/events")
        );
        if (result.ok) {
            console.log(result.result);
            result.result.forEach((event) => {
                event.start = new Date(event.start);
                if (event.end) {
                    event.end = new Date(event.end);
                }
            });
            console.log(result.result);
            // const resultjson = JSON.stringify(result.result);
            // console.log(JSON.parse(resultjson));
            // console.log(JSON.parse(result.result))
            // this.events = JSON.parse(resultjson);
            this.events = result.result;
            console.log(this.events);
            this.refresh();
        } else {
            console.error(result.result.error.error);
        }
    }

    async saveChanges() {
        console.log(this.events);
        console.log(JSON.stringify(this.events));

        if (this.events.length > 0) {
            const result = await toPromise(
                this.http.post<CalendarEvent[]>("/calendar/events", {
                    events: JSON.stringify(this.events),
                })
            );
            // TODO: handle server responses properly
            if (result.ok) {
                console.log("events sent");
                console.log(result.result);
            } else {
                console.error(result.result.error.error);
            }
        }
    }
}

@NgModule({
    imports: [
        BrowserAnimationsModule,
        CommonModule,
        BrowserModule,
        HttpClientModule,
        FormsModule,
        CalendarModule.forRoot({
            provide: DateAdapter,
            useFactory: adapterFactory,
        }),
        CalendarHeaderModule,
    ],
    declarations: [CalendarComponent],
    exports: [CalendarComponent],
})
export class KATTIModule implements DoBootstrap {
    ngDoBootstrap(appRef: ApplicationRef): void {}
}

const angularJsModule = createDowngradedModule((extraProviders) =>
    platformBrowserDynamic(extraProviders).bootstrapModule(KATTIModule)
);

doDowngrade(angularJsModule, "timCalendar", CalendarComponent);

export const moduleDefs = [angularJsModule];
