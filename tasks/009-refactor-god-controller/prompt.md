`OrderController::store()` in `app/Http/Controllers/Api/OrderController.php`
does far too much inline (validation, product lookup, pricing, stock,
payment, persistence, notification, serialization).

Refactor the app toward a clean architecture:

- `App\Http\Requests\StoreOrderRequest` (FormRequest) for validation
- `App\Services\OrderService` to orchestrate, with a public `place()` method
- `App\Services\PricingService` pure (no model, no facade, no DB)
- `App\Services\StockService`
- `App\Services\PaymentGateway` (interface) implemented by `FakePaymentGateway`,
  bound in `AppServiceProvider`
- `App\Http\Resources\OrderResource` (extends JsonResource) for the API output
- `OrderController::store()` must become thin (<= 20 significant lines)
  and must no longer import `App\Models\*` or `DB::`

All existing tests must still pass (Feature AND Architecture).
Do not modify the tests under `tests/`.
