<?php

namespace Tests\Feature;

use App\Models\Order;
use App\Models\Payment;
use App\Models\Product;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class OrderApiTest extends TestCase
{
    use RefreshDatabase;

    private function basePayload(User $user, array $items, string $token = 'tok_ok'): array
    {
        return [
            'user_id' => $user->id,
            'items' => $items,
            'payment_method' => 'card',
            'payment_token' => $token,
        ];
    }

    public function test_creates_order_with_valid_payload(): void
    {
        $user = User::factory()->create();
        $p1 = Product::factory()->create(['price_cents' => 1000, 'stock' => 10]);
        $p2 = Product::factory()->create(['price_cents' => 2500, 'stock' => 5]);

        $payload = $this->basePayload($user, [
            ['product_id' => $p1->id, 'quantity' => 2],
            ['product_id' => $p2->id, 'quantity' => 1],
        ]);

        $response = $this->postJson('/api/orders', $payload);

        $response->assertStatus(201)
            ->assertJsonPath('order.user_id', $user->id)
            ->assertJsonPath('payment.status', 'ok');

        // subtotal = 2*1000 + 1*2500 = 4500
        $response->assertJsonPath('order.subtotal_cents', 4500);

        // Stock decremented
        $this->assertEquals(8, $p1->fresh()->stock);
        $this->assertEquals(4, $p2->fresh()->stock);

        // Persisted
        $this->assertDatabaseCount('orders', 1);
        $this->assertDatabaseCount('payments', 1);
    }

    public function test_calculates_pricing_with_tax(): void
    {
        $user = User::factory()->create();
        $product = Product::factory()->create(['price_cents' => 5000, 'stock' => 10]);

        $payload = $this->basePayload($user, [
            ['product_id' => $product->id, 'quantity' => 1],
        ]);

        $response = $this->postJson('/api/orders', $payload);

        // subtotal = 5000, tax = 1000 (20%), no discount, total = 6000
        $response->assertStatus(201)
            ->assertJsonPath('order.subtotal_cents', 5000)
            ->assertJsonPath('order.tax_cents', 1000)
            ->assertJsonPath('order.discount_cents', 0)
            ->assertJsonPath('order.total_cents', 6000);
    }

    public function test_applies_discount_above_threshold(): void
    {
        $user = User::factory()->create();
        $product = Product::factory()->create(['price_cents' => 6000, 'stock' => 10]);

        $payload = $this->basePayload($user, [
            ['product_id' => $product->id, 'quantity' => 2],
        ]);

        $response = $this->postJson('/api/orders', $payload);

        // subtotal = 12000 (> 10000) → discount = 1200 (10%)
        // tax = 2400 (20% of subtotal)
        // total = 12000 + 2400 - 1200 = 13200
        $response->assertStatus(201)
            ->assertJsonPath('order.subtotal_cents', 12000)
            ->assertJsonPath('order.tax_cents', 2400)
            ->assertJsonPath('order.discount_cents', 1200)
            ->assertJsonPath('order.total_cents', 13200);
    }

    public function test_rejects_insufficient_stock(): void
    {
        $user = User::factory()->create();
        $product = Product::factory()->create(['price_cents' => 1000, 'stock' => 2]);

        $payload = $this->basePayload($user, [
            ['product_id' => $product->id, 'quantity' => 5],
        ]);

        $response = $this->postJson('/api/orders', $payload);

        $response->assertStatus(422);

        $this->assertEquals(2, $product->fresh()->stock);
        $this->assertDatabaseCount('orders', 0);
        $this->assertDatabaseCount('payments', 0);
    }

    public function test_rejects_invalid_payload(): void
    {
        $user = User::factory()->create();

        // Missing items + payment_token
        $response = $this->postJson('/api/orders', [
            'user_id' => $user->id,
            'payment_method' => 'card',
        ]);

        $response->assertStatus(422);
    }

    public function test_rolls_back_on_payment_failure(): void
    {
        config(['payments.force_status' => 'failed']);

        $user = User::factory()->create();
        $product = Product::factory()->create(['price_cents' => 1000, 'stock' => 10]);

        $payload = $this->basePayload($user, [
            ['product_id' => $product->id, 'quantity' => 3],
        ]);

        $response = $this->postJson('/api/orders', $payload);

        $response->assertStatus(402);

        // Order, payment, and stock all rolled back
        $this->assertEquals(10, $product->fresh()->stock);
        $this->assertDatabaseCount('orders', 0);
        $this->assertDatabaseCount('payments', 0);
    }

    public function test_unknown_product_returns_404(): void
    {
        $user = User::factory()->create();

        $payload = $this->basePayload($user, [
            ['product_id' => 999999, 'quantity' => 1],
        ]);

        $response = $this->postJson('/api/orders', $payload);

        $response->assertStatus(404);
        $this->assertDatabaseCount('orders', 0);
    }
}
