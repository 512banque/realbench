This workspace contains a small Laravel 8 application (minimal skeleton, ~20
files, one users CRUD endpoint).

Migrate the application to Laravel 12 so that `vendor/bin/phpunit` passes with
`laravel/framework: ^12.0` once `composer install` has been run.

What must change (at minimum):

- `composer.json`: `laravel/framework: ^12.0`, `phpunit/phpunit: ^11.0`, required
  PHP version `^8.2`, and all other deps updated or removed
- Adopt the new Laravel 11+ structure: route everything through
  `bootstrap/app.php` (`withRouting`, `withMiddleware`, `withExceptions` style).
  Remove `app/Http/Kernel.php`, `app/Console/Kernel.php`,
  `app/Exceptions/Handler.php`, `app/Providers/RouteServiceProvider.php`
- `tests/TestCase.php` simplified (no more `CreatesApplication` trait), remove
  `tests/CreatesApplication.php`
- `phpunit.xml` in PHPUnit 11 format
- Adapt whatever else is needed so the existing tests keep passing

Do not modify the tests in `tests/Feature/`. They define the business contract
the app must respect.
