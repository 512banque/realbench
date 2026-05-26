<?php

namespace App\Services;

use App\Exceptions\PaymentFailedException;
use App\Models\Order;
use App\Models\Payment;
use App\Models\Product;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

class OrderService
{
    public function __construct(
        private PricingService $pricing,
        private StockService $stock,
        private PaymentGateway $gateway,
    ) {
    }

    /**
     * Place an order: validates resources, computes pricing, decrements stock,
     * charges the payment gateway, persists order + payment and emits a
     * notification log entry. Wraps everything in a DB transaction; rolls
     * back and throws PaymentFailedException on payment failure.
     *
     * @param  array<int, array{product_id: int, quantity: int}>  $items
     */
    public function place(int $userId, array $items, string $paymentMethod, string $paymentToken): Order
    {
        $user = User::findOrFail($userId);

        // Fetch products eagerly before opening the transaction so 404s
        // surface as ModelNotFoundException, not inside a rollback.
        $lines = [];
        $pricingLines = [];
        foreach ($items as $item) {
            $product = Product::findOrFail($item['product_id']);
            $lines[] = ['product' => $product, 'quantity' => (int) $item['quantity']];
            $pricingLines[] = [
                'price_cents' => $product->price_cents,
                'quantity' => (int) $item['quantity'],
            ];
        }

        $pricing = $this->pricing->compute($pricingLines);

        return DB::transaction(function () use ($user, $lines, $pricing, $paymentToken) {
            $this->stock->reserve($lines);

            $order = Order::create([
                'user_id' => $user->id,
                'subtotal_cents' => $pricing['subtotal_cents'],
                'tax_cents' => $pricing['tax_cents'],
                'discount_cents' => $pricing['discount_cents'],
                'total_cents' => $pricing['total_cents'],
                'status' => 'pending',
            ]);

            $charge = $this->gateway->charge($pricing['total_cents'], $paymentToken);

            if (($charge['status'] ?? null) !== 'ok') {
                throw new PaymentFailedException('Payment gateway rejected the charge.');
            }

            $payment = Payment::create([
                'order_id' => $order->id,
                'amount_cents' => $pricing['total_cents'],
                'status' => $charge['status'],
                'transaction_id' => $charge['transaction_id'],
            ]);

            $order->status = 'paid';
            $order->save();

            Log::info("Order placed for user {$user->id}, order {$order->id}, total {$pricing['total_cents']}");

            // Attach the payment so the resource can render it without an extra query.
            $order->setRelation('payment', $payment);

            return $order;
        });
    }
}
