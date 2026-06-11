import logging

from rich.logging import RichHandler

from process import Episode, strip_episode

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        RichHandler(
            rich_tracebacks=True,
            log_time_format="[%m/%d/%y %H:%M:%S.%f]",
        )
    ],
)


def main():
    ep = Episode(
        title="testing",
        description="gm",
        pub_date="gm ur mom",
        mp3_link="https://drive.google.com/uc?export=download&id=11SkRJc7HZ-EqLZ6wOGRLX5USPbiy8VVp",
        transcript_link="https://gist.githubusercontent.com/mud2monarch/c576275aa73ff66a075f76a5462867cd/raw/fd2e7e2bd980df2589ac2271c4a642f20b407fea/gistfile1.txt",
    )

    output_path = strip_episode(ep)
    print(f"Wrote ad-free episode to {output_path}.")


if __name__ == "__main__":
    main()
