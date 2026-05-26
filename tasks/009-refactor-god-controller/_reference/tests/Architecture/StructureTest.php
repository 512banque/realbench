<?php

namespace Tests\Architecture;

use App\Http\Controllers\Api\OrderController;
use ReflectionClass;
use Tests\TestCase;

/**
 * Static structural assertions on the refactor target.
 *
 * These tests intentionally do NOT boot the application or touch the
 * database — they read files and reflect on classes. They must fail on
 * the initial "god controller" workspace and pass on the refactored
 * solution.
 */
class StructureTest extends TestCase
{
    private string $appPath;

    protected function setUp(): void
    {
        parent::setUp();
        $this->appPath = base_path('app');
    }

    public function test_store_order_request_exists(): void
    {
        $class = 'App\\Http\\Requests\\StoreOrderRequest';
        $this->assertTrue(
            class_exists($class),
            "Expected $class to exist."
        );

        $rc = new ReflectionClass($class);
        $this->assertTrue(
            $rc->isSubclassOf('Illuminate\\Foundation\\Http\\FormRequest'),
            "$class must extend Illuminate\\Foundation\\Http\\FormRequest."
        );
        $this->assertTrue(
            $rc->hasMethod('rules'),
            "$class must define a rules() method."
        );
    }

    public function test_order_service_exists_with_place_method(): void
    {
        $class = 'App\\Services\\OrderService';
        $this->assertTrue(class_exists($class), "Expected $class to exist.");

        $rc = new ReflectionClass($class);
        $this->assertTrue($rc->hasMethod('place'), "$class must have a place() method.");

        $method = $rc->getMethod('place');
        $this->assertTrue($method->isPublic(), 'place() must be public.');
        $this->assertGreaterThanOrEqual(
            3,
            $method->getNumberOfParameters(),
            'place() must take at least 3 parameters (user id, items, payment data).'
        );
    }

    public function test_pricing_service_is_pure(): void
    {
        $class = 'App\\Services\\PricingService';
        $this->assertTrue(class_exists($class), "Expected $class to exist.");

        $rc = new ReflectionClass($class);
        $this->assertTrue($rc->hasMethod('compute'), 'PricingService must have a compute() method.');

        $file = $rc->getFileName();
        $this->assertIsString($file, 'Could not resolve PricingService source file.');

        $source = file_get_contents($file);

        // Pure service: no model imports, no facades, no DB.
        $this->assertDoesNotMatchRegularExpression(
            '/App\\\\Models\\\\/',
            $source,
            'PricingService must not depend on App\\Models.'
        );
        $this->assertDoesNotMatchRegularExpression(
            '/Illuminate\\\\Support\\\\Facades\\\\/',
            $source,
            'PricingService must not use Illuminate facades.'
        );
        $this->assertDoesNotMatchRegularExpression(
            '/\bDB::/',
            $source,
            'PricingService must not use the DB facade.'
        );
    }

    public function test_payment_gateway_interface_exists(): void
    {
        $iface = 'App\\Services\\PaymentGateway';
        $this->assertTrue(
            interface_exists($iface),
            "Expected $iface to exist as an interface."
        );

        $rc = new ReflectionClass($iface);
        $this->assertTrue($rc->isInterface(), "$iface must be an interface.");
        $this->assertTrue($rc->hasMethod('charge'), 'PaymentGateway must declare a charge() method.');
    }

    public function test_fake_payment_gateway_implements_interface(): void
    {
        $impl = 'App\\Services\\FakePaymentGateway';
        $iface = 'App\\Services\\PaymentGateway';

        $this->assertTrue(class_exists($impl), "Expected $impl to exist.");
        $this->assertTrue(interface_exists($iface), "Expected $iface to exist.");

        $implements = class_implements($impl) ?: [];
        $this->assertContains(
            $iface,
            $implements,
            "$impl must implement $iface."
        );
    }

    public function test_order_resource_exists(): void
    {
        $class = 'App\\Http\\Resources\\OrderResource';
        $this->assertTrue(class_exists($class), "Expected $class to exist.");

        $rc = new ReflectionClass($class);
        $this->assertTrue(
            $rc->isSubclassOf('Illuminate\\Http\\Resources\\Json\\JsonResource'),
            "$class must extend JsonResource."
        );
    }

    public function test_order_controller_store_is_thin(): void
    {
        $controllerFile = $this->appPath.'/Http/Controllers/Api/OrderController.php';
        $this->assertFileExists($controllerFile);

        $body = $this->extractMethodBody($controllerFile, 'store');
        $this->assertNotNull($body, 'Could not locate OrderController::store() body.');

        $count = $this->countSignificantLines($body);

        $this->assertLessThanOrEqual(
            20,
            $count,
            "OrderController::store() must be <= 20 significant lines (currently $count).\n"
            ."Significant lines exclude blank lines and lines starting with // or * or /* or *.\n"
            ."Body was:\n".$body
        );
    }

    public function test_order_controller_does_not_import_models_directly(): void
    {
        $controllerFile = $this->appPath.'/Http/Controllers/Api/OrderController.php';
        $source = file_get_contents($controllerFile);

        foreach (['Order', 'Payment', 'Product'] as $model) {
            $this->assertDoesNotMatchRegularExpression(
                '/^use\s+App\\\\Models\\\\'.$model.'\s*;/m',
                $source,
                "OrderController must not import App\\Models\\$model directly."
            );
        }
    }

    public function test_order_controller_does_not_use_db_facade(): void
    {
        $controllerFile = $this->appPath.'/Http/Controllers/Api/OrderController.php';
        $source = file_get_contents($controllerFile);

        $this->assertDoesNotMatchRegularExpression(
            '/^use\s+Illuminate\\\\Support\\\\Facades\\\\DB\s*;/m',
            $source,
            'OrderController must not import the DB facade.'
        );

        $this->assertDoesNotMatchRegularExpression(
            '/\bDB::/',
            $source,
            'OrderController must not call DB:: directly.'
        );
    }

    /**
     * Extracts the *body* of a method (text between the opening { after the
     * signature and its matching closing }). Returns null if not found.
     */
    private function extractMethodBody(string $file, string $methodName): ?string
    {
        $code = file_get_contents($file);
        if ($code === false) {
            return null;
        }

        // Find the method signature.
        if (! preg_match('/function\s+'.preg_quote($methodName, '/').'\s*\(/', $code, $m, PREG_OFFSET_CAPTURE)) {
            return null;
        }

        $offset = $m[0][1];

        // Walk forward to the first '{' after the signature, then brace-match.
        $len = strlen($code);
        $i = $offset;

        // Find the opening brace of the body.
        while ($i < $len && $code[$i] !== '{') {
            $i++;
        }
        if ($i >= $len) {
            return null;
        }

        $bodyStart = $i + 1;
        $depth = 1;
        $i = $bodyStart;

        // Simple state machine to skip strings and comments while brace-matching.
        while ($i < $len && $depth > 0) {
            $ch = $code[$i];
            $next = $i + 1 < $len ? $code[$i + 1] : '';

            // Line comment
            if ($ch === '/' && $next === '/') {
                while ($i < $len && $code[$i] !== "\n") {
                    $i++;
                }
                continue;
            }

            // Block comment
            if ($ch === '/' && $next === '*') {
                $i += 2;
                while ($i < $len - 1 && ! ($code[$i] === '*' && $code[$i + 1] === '/')) {
                    $i++;
                }
                $i += 2;
                continue;
            }

            // Single-quoted string
            if ($ch === "'") {
                $i++;
                while ($i < $len) {
                    if ($code[$i] === '\\') {
                        $i += 2;
                        continue;
                    }
                    if ($code[$i] === "'") {
                        $i++;
                        break;
                    }
                    $i++;
                }
                continue;
            }

            // Double-quoted string
            if ($ch === '"') {
                $i++;
                while ($i < $len) {
                    if ($code[$i] === '\\') {
                        $i += 2;
                        continue;
                    }
                    if ($code[$i] === '"') {
                        $i++;
                        break;
                    }
                    $i++;
                }
                continue;
            }

            if ($ch === '{') {
                $depth++;
            } elseif ($ch === '}') {
                $depth--;
                if ($depth === 0) {
                    return substr($code, $bodyStart, $i - $bodyStart);
                }
            }

            $i++;
        }

        return null;
    }

    /**
     * Counts significant lines: trimmed, non-empty, and not starting with a
     * comment marker ( //, #, /*, *, *\/ ).
     */
    private function countSignificantLines(string $body): int
    {
        $count = 0;
        foreach (preg_split("/\r?\n/", $body) as $line) {
            $trim = trim($line);
            if ($trim === '') {
                continue;
            }
            if (str_starts_with($trim, '//')
                || str_starts_with($trim, '#')
                || str_starts_with($trim, '/*')
                || str_starts_with($trim, '*/')
                || str_starts_with($trim, '*')) {
                continue;
            }
            $count++;
        }

        return $count;
    }
}
