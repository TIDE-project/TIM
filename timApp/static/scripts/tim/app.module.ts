import {BrowserModule} from "@angular/platform-browser";
import {ApplicationRef, DoBootstrap, NgModule} from "@angular/core";
import {FormsModule} from "@angular/forms";
import {HeaderComponent} from "tim/header/header.component";
import {HttpClientModule, HTTP_INTERCEPTORS} from "@angular/common/http";
import {CreateItemComponent} from "tim/item/create-item.component";
import {ErrorStateDirective} from "tim/ui/error-state.directive";
import {ErrorMessageComponent} from "tim/ui/error-message.component";
import {ShortNameDirective} from "tim/ui/short-name.directive";
import {LocationDirective} from "tim/ui/location.directive";
import {TimAlertComponent} from "tim/ui/tim-alert.component";
import {TimUtilityModule} from "tim/ui/tim-utility.module";
import {TimeStampToMomentConverter} from "tim/util/time-stamp-to-moment-converter.service";

// noinspection AngularInvalidImportedOrDeclaredSymbol
@NgModule({
    declarations: [
        CreateItemComponent,
        ErrorMessageComponent,
        ErrorStateDirective,
        HeaderComponent,
        LocationDirective,
        ShortNameDirective,
        TimAlertComponent,
    ],
    imports: [
        BrowserModule,
        HttpClientModule,
        FormsModule,
        TimUtilityModule,
    ],
    providers: [
        {provide: HTTP_INTERCEPTORS, useClass: TimeStampToMomentConverter, multi: true},
    ],
    bootstrap: [],
})
export class AppModule implements DoBootstrap {
    ngDoBootstrap(appRef: ApplicationRef) {
    }
}
