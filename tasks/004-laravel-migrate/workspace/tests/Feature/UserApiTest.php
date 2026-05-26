<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class UserApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_index_returns_all_users(): void
    {
        User::factory()->count(3)->create();

        $this->getJson('/api/users')
            ->assertOk()
            ->assertJsonCount(3);
    }

    public function test_store_creates_user(): void
    {
        $payload = ['name' => 'Alice', 'email' => 'alice@example.com'];

        $this->postJson('/api/users', $payload)
            ->assertCreated()
            ->assertJsonPath('name', 'Alice')
            ->assertJsonPath('email', 'alice@example.com');

        $this->assertDatabaseHas('users', ['email' => 'alice@example.com']);
    }

    public function test_store_rejects_duplicate_email(): void
    {
        User::factory()->create(['email' => 'taken@example.com']);

        $this->postJson('/api/users', ['name' => 'Bob', 'email' => 'taken@example.com'])
            ->assertUnprocessable();
    }

    public function test_show_returns_a_user(): void
    {
        $user = User::factory()->create();

        $this->getJson("/api/users/{$user->id}")
            ->assertOk()
            ->assertJsonPath('id', $user->id)
            ->assertJsonPath('email', $user->email);
    }

    public function test_destroy_removes_a_user(): void
    {
        $user = User::factory()->create();

        $this->deleteJson("/api/users/{$user->id}")
            ->assertNoContent();

        $this->assertDatabaseMissing('users', ['id' => $user->id]);
    }
}
