<?php

namespace App\Services;

/**
 * Pure pricing service. No models, no database, no facades.
 *
 * Pricing rules:
 *   - tax = 20% of subtotal (rounded)
 *   - discount = 10% of subtotal (rounded) when subtotal > 10000 cents, else 0
 *   - total = subtotal + tax - discount
 */
class PricingService
{
    /**
     * Each line must contain integer 'price_cents' and integer 'quantity'.
     *
     * @param  array<int, array{price_cents: int, quantity: int}>  $lines
     * @return array{subtotal_cents: int, tax_cents: int, discount_cents: int, total_cents: int}
     */
    public function compute(array $lines): array
    {
        $subtotal = 0;
        foreach ($lines as $line) {
            $subtotal += (int) $line['price_cents'] * (int) $line['quantity'];
        }

        $tax = (int) round($subtotal * 0.20);

        $discount = 0;
        if ($subtotal > 10000) {
            $discount = (int) round($subtotal * 0.10);
        }

        $total = $subtotal + $tax - $discount;

        return [
            'subtotal_cents' => $subtotal,
            'tax_cents' => $tax,
            'discount_cents' => $discount,
            'total_cents' => $total,
        ];
    }
}
