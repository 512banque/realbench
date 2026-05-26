<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Order;
use App\Models\Payment;
use App\Models\Product;
use App\Models\User;
use App\Services\FakePaymentGateway;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Validation\ValidationException;

/**
 * God controller. Does everything inline in store():
 *   - validation
 *   - user lookup
 *   - product lookup + stock check
 *   - pricing (subtotal, tax, discount, total)
 *   - order persistence
 *   - stock decrement
 *   - payment via FakePaymentGateway
 *   - payment persistence
 *   - notification (log)
 *   - response serialization
 */
class OrderController extends Controller
{
    public function store(Request $request)
    {
        // 1. Inline validation rules
        $validated = $request->validate([
            'user_id' => 'required|integer',
            'items' => 'required|array|min:1',
            'items.*.product_id' => 'required|integer',
            'items.*.quantity' => 'required|integer|min:1',
            'payment_method' => 'required|string|in:card,paypal',
            'payment_token' => 'required|string',
        ]);

        // 2. Lookup user
        $user = User::findOrFail($validated['user_id']);

        // 3. Open a transaction so we can roll back on payment failure
        DB::beginTransaction();

        try {
            // 4. Iterate items, fetch products, check stock, accumulate subtotal
            $subtotalCents = 0;
            $lineItems = [];

            foreach ($validated['items'] as $item) {
                $product = Product::findOrFail($item['product_id']);

                if ($product->stock < $item['quantity']) {
                    DB::rollBack();
                    throw ValidationException::withMessages([
                        'items' => "Insufficient stock for product {$product->id}",
                    ]);
                }

                $lineSubtotal = $product->price_cents * $item['quantity'];
                $subtotalCents += $lineSubtotal;

                $lineItems[] = [
                    'product' => $product,
                    'quantity' => $item['quantity'],
                    'subtotal' => $lineSubtotal,
                ];
            }

            // 5. Pricing computations inline:
            //    - 20% tax
            //    - 10% discount if subtotal > 10000
            $taxCents = (int) round($subtotalCents * 0.20);

            $discountCents = 0;
            if ($subtotalCents > 10000) {
                $discountCents = (int) round($subtotalCents * 0.10);
            }

            $totalCents = $subtotalCents + $taxCents - $discountCents;

            // 6. Create the Order
            $order = Order::create([
                'user_id' => $user->id,
                'subtotal_cents' => $subtotalCents,
                'tax_cents' => $taxCents,
                'discount_cents' => $discountCents,
                'total_cents' => $totalCents,
                'status' => 'pending',
            ]);

            // 7. Decrement stock inline (no domain service)
            foreach ($lineItems as $line) {
                $line['product']->stock = $line['product']->stock - $line['quantity'];
                $line['product']->save();
            }

            // 8. "Charge" via FakePaymentGateway, inline-instantiated
            $gateway = new FakePaymentGateway();
            $chargeResult = $gateway->charge($totalCents, $validated['payment_token']);

            if ($chargeResult['status'] !== 'ok') {
                // Roll back order + stock decrement
                DB::rollBack();

                return response()->json([
                    'message' => 'Payment failed',
                    'status' => 'failed',
                ], 402);
            }

            // 9. Persist payment row
            $payment = Payment::create([
                'order_id' => $order->id,
                'amount_cents' => $totalCents,
                'status' => $chargeResult['status'],
                'transaction_id' => $chargeResult['transaction_id'],
            ]);

            // 10. Mark order paid
            $order->status = 'paid';
            $order->save();

            // 11. "Notify" via log
            Log::info("Order placed for user {$user->id}, order {$order->id}, total {$totalCents}");

            DB::commit();

            // 12. Inline JSON response (no Resource class)
            return response()->json([
                'order' => [
                    'id' => $order->id,
                    'user_id' => $order->user_id,
                    'subtotal_cents' => $order->subtotal_cents,
                    'tax_cents' => $order->tax_cents,
                    'discount_cents' => $order->discount_cents,
                    'total_cents' => $order->total_cents,
                    'status' => $order->status,
                ],
                'payment' => [
                    'id' => $payment->id,
                    'amount_cents' => $payment->amount_cents,
                    'status' => $payment->status,
                    'transaction_id' => $payment->transaction_id,
                ],
            ], 201);
        } catch (ValidationException $e) {
            // Validation thrown after rollback above; rethrow so Laravel handles 422
            throw $e;
        } catch (\Throwable $e) {
            if (DB::transactionLevel() > 0) {
                DB::rollBack();
            }
            throw $e;
        }
    }
}
